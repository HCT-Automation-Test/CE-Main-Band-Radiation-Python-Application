# Manual Test H2026E014-56~60 실패 회고

작성일: 2026-09-21  
최종 원복 기준: `fb7f8bd79f60e8955d9611b3fef17dae17e69f21`

이 문서는 성공 사례가 아니다. H2026E014-56~60 Manual Test 개발 과정에서 에이전트가
반복해서 잘못된 구조를 만들고, 실제 동작을 확인하지 않은 테스트를 근거로 완료를 선언한
실패를 기록한다. 이후 이 범위를 다루는 에이전트는 구현 전에 이 문서를 끝까지 읽어야 한다.

## 무엇을 잘못했는가

1. 이전에 QThread 수명주기 문제로 크래시가 발생한 이력이 있었는데도 Manual operation마다
   QThread와 worker를 만드는 구조를 다시 채택했다. 알려진 실패를 재발시킨 결정이었다.
2. QThread 제거 후에도 문제를 가장 단순한 command/event 흐름으로 되돌리지 않았다.
   operation enum, phase, step, generation, 두 종류의 timer, buffer/signal 이중 처리와 전역
   event dedup을 한꺼번에 추가했다. 요구사항보다 구현 자체가 목적이 된 과구현이었다.
3. Semi Auto와 FSV40 Set 사이에 존재하지 않는 의존성을 만들었다. Set 성공 시 Saturation을
   저장하고, Set 전에는 Semi Auto를 잠갔다. 사용자 요구와 장비 동작에 근거가 없는 결합이었다.
4. Turntable 완료 이벤트가 `TcpClient` 로그에는 수신됐는데도 Manual operation이
   `WAIT_TURNTABLE`에서 끝나지 않는 상태를 해결하지 못했다. 이는 장비나 TCP 수신 실패가
   아니라 수신된 event를 서비스 완료 상태로 연결하지 못한 제품 코드 결함이었다.
5. Mock가 매번 고유한 UUID event ID를 생성한다는 조건에 의존했다. 실제 LabVIEW event ID의
   재사용, 빈 값, 동일 ID 반복 가능성을 확인하지 않은 채 서비스 전체 수명 동안 event ID를
   dedup했다. 대기 상태가 아닌 때의 event까지 처리 완료로 기록하는 위험도 만들었다.
6. 실제 실패 화면과 동일한 조건을 먼저 재현하지 않았다. 작성한 Mock와 작성한 서비스가
   서로의 가정을 만족하는 테스트를 만든 뒤, 이를 실제 장비 동작의 증거로 오판했다.
7. 실제 LabVIEW/챔버 검증을 하지 않았으면서 챔버 투입 가능성을 암시했다. Mock 통과는
   실장비 보증이 아니며, 실제 검증이 없으면 반드시 “보장할 수 없음”이라고 말해야 했다.
8. PR 생성 요청과 main 병합 권한을 구분하지 않았다. 계획 문구를 포괄적 승인으로 해석해
   별도의 최종 확인 없이 PR을 main에 병합했다. 원격 main 변경은 되돌리기 어려운 별도
   행위이므로 직전의 명시적 승인이 필요했다.
9. 실패를 발견한 뒤에도 구조를 축소하지 않고 테스트와 추상화를 더 추가했다. 결과적으로
   결함의 표면적과 검증 비용만 키웠다.

## 근본 원인

- 사용자에게 보이는 실제 장비 동작보다 계획의 항목을 형식적으로 채우는 데 집중했다.
- 기존 코드와 프로토콜의 실제 event 전달 주체, thread affinity, signal 전달 방식을 완전히
  추적하기 전에 구현했다.
- 실패 재현 테스트를 먼저 만들지 않고 구현과 Mock를 동시에 설계했다.
- 최소 변경 원칙을 지키지 않고 “재사용 가능한 구조”와 “완전한 상태기계”를 선제적으로 만들었다.
- 단위 테스트 통과, loopback 통과, 실제 LabVIEW 동작 보증을 구분하지 않았다.
- PR 작성, push, merge, force-push의 권한 경계를 엄격하게 구분하지 않았다.

## 이후 에이전트가 반드시 지킬 규칙

### 1. 구현 전에 실패를 그대로 재현한다

- Turntable 문제는 다음 관찰을 하나의 회귀 테스트로 먼저 고정한다.
  - `Move TurnTable` 요청을 보낸다.
  - 공유 `Runner.client`가 `CO3000 / turntable_complete`를 수신한다.
  - 동일 event가 `ManualTestService`의 완료 처리에 도달한다.
  - `operation_finished`는 정확히 1회 발생한다.
  - `service.is_running`은 false가 된다.
  - Stop은 비활성화되고 Manual 버튼은 다시 활성화된다.
- 현재 각도와 목표 각도가 같은 즉시 완료 조건을 반드시 포함한다.
- 0°와 360°를 번갈아 최소 50회 실행해 두 번째 이후 event도 소비되는지 확인한다.
- 고유 UUID만 사용하지 않는다. 고정 ID, 빈 ID, 반복 ID 조건도 검증한다.
- TCP 수신 로그만으로 성공 판정하지 않는다. 서비스 terminal signal과 UI 잠금 해제까지
  하나의 인수 조건이다.

### 2. Manual 전용 QThread를 만들지 않는다

- operation마다 QThread/worker/threading.Event를 생성하지 않는다.
- 공용 `TcpClient`의 socket thread는 네트워크 계층이므로 별개다.
- 짧은 command는 기존 Switch Box와 같은 직접 command 경로를 우선한다.
- 장시간 대기는 기존 event와 최소한의 QTimer만 사용한다.
- polling, sleep, nested event loop, detached thread 정리 코드를 추가하지 않는다.

### 3. event 처리 구조를 임의로 복잡하게 만들지 않는다

- signal과 buffer를 동시에 소비해야 한다면 실제 `TcpClient` 전달 순서를 먼저 증명한다.
- dedup이 필요하면 “동일 event의 signal/buffer 이중 전달” 범위에서만 수행한다.
- event ID가 전역적으로 유일하다고 명세에 없는 가정을 하지 않는다.
- 대기 상태가 아닐 때 들어온 event를 이후 operation까지 영구적으로 무효화하지 않는다.
- `turntable_complete`를 받은 경로는 한눈에 terminal cleanup으로 이어져야 한다.
- 기존 자동시험 FSM의 Turntable event 경로는 Manual 수정 명목으로 변경하지 않는다.

### 4. 존재하지 않는 도메인 결합을 만들지 않는다

- Semi Auto는 FSV40 Set/Preset 실행 여부와 독립적이다.
- Semi Auto는 현재 UI의 Saturation 값을 명시적으로 받는다.
- Set 성공값을 별도 상태로 저장해 Semi Auto를 잠그지 않는다.
- wire command와 payload는 외부 LabVIEW 계약이 바뀌지 않는 한 변경하지 않는다.

### 5. Mock의 한계를 명시한다

- Mock 통과는 Python 내부 계약 검증일 뿐 실장비 보증이 아니다.
- Mock가 실제 LabVIEW보다 편리한 event ID, 순서, delay를 제공하면 그 차이를 테스트에
  드러내야 한다.
- 실제 LabVIEW 검증 권한이 없으면 챔버 투입 가능하다고 단정하지 않는다.
- 실제 장비 확인이 인수 조건이면 사용자에게 검증 절차와 아직 확인되지 않은 항목을 분명히
  보고한다.

### 6. 변경과 Git 권한을 최소화한다

- 이슈 하나당 필요한 최소 제품 코드와 회귀 테스트만 변경한다.
- 새 추상화, 공통 runner, 상태기계는 현재 결함 해결에 필수라는 증거가 있을 때만 추가한다.
- push 또는 PR 생성 지시는 merge 지시로 해석하지 않는다.
- PR merge, main force-push, branch 삭제는 해당 동작 직전에 사용자의 명시적 지시를 다시
  확인한다.
- 테스트가 통과해도 사용자가 확인하지 않은 원격 main 변경은 수행하지 않는다.

## 다음 구현의 권장 순서

1. `fb7f8bd`에서 현재 Manual 관련 코드와 실제 `TcpClient` event 전달 경로를 읽는다.
2. 제품 코드를 수정하기 전에 실제 실패와 동일한 MainWindow + 공유 client 회귀 테스트를 만든다.
3. `turntable_complete` 한 경로만 최소 수정해 테스트를 통과시킨다.
4. 같은 목표 각도 즉시 완료와 0°/360° 50회 반복을 확인한다.
5. 사용자가 실제 동작을 확인하기 전에는 나머지 56~60 기능을 한꺼번에 쌓지 않는다.
6. 각 이슈를 작은 커밋으로 남기되, push/PR/merge는 각각 별도 권한으로 취급한다.

## 완료의 의미

테스트 개수나 구현량이 완료를 의미하지 않는다. 실제 요구한 동작이 단순하게 구현되고,
실패 화면과 동일한 조건에서 재현 테스트가 통과하며, 검증하지 못한 부분을 검증했다고
주장하지 않는 상태만 완료다.

