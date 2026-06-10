from __future__ import annotations

import argparse
import json
import shlex
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any, TextIO

from app.models.enums import AntennaPol, FilterPath, InputPath, Modulation
from app.models.test_range import get_test_range
from app.net import commands
from app.net.protocol import Event, Response
from app.net.tcp_client import TcpClient


_COMMAND_EQUIPMENT_ERROR = "equipment_error"


@dataclass
class Interaction:
    target: str
    command: str
    params: dict[str, Any]
    response: Response | None = None
    error: BaseException | None = None


class RecordingClient:
    def __init__(self, client: Any, interactions: list[Interaction]) -> None:
        self._client = client
        self._interactions = interactions

    def send_request(
        self,
        target: str,
        command: str,
        params: dict[str, Any] | None = None,
        timeout: float = 60.0,
    ) -> Response:
        interaction = Interaction(target=target, command=command, params=params or {})
        self._interactions.append(interaction)
        try:
            response = self._client.send_request(
                target,
                command,
                params or {},
                timeout=timeout,
            )
        except BaseException as exc:
            interaction.error = exc
            raise
        interaction.response = response
        return response


class MockLvClientConsole:
    def __init__(
        self,
        client: Any,
        *,
        output: TextIO = sys.stdout,
        auto_events: bool = True,
    ) -> None:
        self._client = client
        self._recording_client = RecordingClient(client, [])
        self._output = output
        self._auto_events = auto_events
        self._event_history: list[Event] = []
        self._event_condition = threading.Condition()
        self._print_lock = threading.Lock()
        self._stop_events = threading.Event()
        self._event_thread: threading.Thread | None = None

    @property
    def event_history(self) -> list[Event]:
        with self._event_condition:
            return list(self._event_history)

    def start_event_watcher(self) -> None:
        if self._event_thread is not None and self._event_thread.is_alive():
            return
        self._stop_events.clear()
        self._event_thread = threading.Thread(target=self._watch_events, daemon=True)
        self._event_thread.start()

    def stop_event_watcher(self) -> None:
        self._stop_events.set()
        if self._event_thread is not None:
            self._event_thread.join(timeout=1.0)
            self._event_thread = None

    def run(self) -> None:
        self._print("Type help for commands. Type quit to exit.")
        while True:
            try:
                line = input("lv> ")
            except (EOFError, KeyboardInterrupt):
                self._print("")
                return
            if not self.execute_line(line):
                return

    def execute_line(self, line: str) -> bool:
        try:
            name, args = parse_line(line)
        except ValueError as exc:
            self._print_error(str(exc))
            return True

        if not name:
            return True
        if name in {"quit", "exit"}:
            return False
        if name == "help":
            self._print_help()
            return True
        if name == "events":
            self._print_events()
            return True

        before = len(self._recording_client._interactions)
        try:
            value = self._dispatch(name, args)
        except Exception as exc:
            self._print_interactions(before)
            self._print_error(str(exc))
            return True

        self._print_interactions(before)
        if value is not None:
            self._print("RETURN   " + _json_dumps(value))
        return True

    def _dispatch(self, name: str, args: dict[str, str]) -> Any:
        if name == "connect":
            return self._connect(args)
        if name == "setup-mt8000":
            return commands.setup_mt8000(
                self._recording_client,
                band=_int_arg(args, "band"),
                bw=_int_arg(args, "bw"),
                modulation=_modulation_arg(args, "modulation"),
                rb_size=_int_arg(args, "rb_size"),
                rb_offset=_int_arg(args, "rb_offset"),
                channel=_int_arg(args, "channel"),
                max_retry_count=_int_arg(args, "max_retry_count", default=3),
                waiting_time=_int_arg(args, "waiting_time", default=5),
            )
        if name == "handover":
            return commands.call_handover(
                self._recording_client,
                mid_channel=_int_arg(args, "mid_channel"),
                band=_int_arg(args, "band"),
                bw=_int_arg(args, "bw"),
                modulation=_modulation_arg(args, "modulation"),
                rb_size=_int_arg(args, "rb_size"),
                rb_offset=_int_arg(args, "rb_offset"),
                channel=_int_arg(args, "channel"),
            )
        if name == "setup-sa-level":
            return commands.setup_sa_startup_levels(
                self._recording_client,
                atten_level_db=_float_arg(args, "atten", "atten_level_db"),
                next_peak_search_level_db=_float_arg(
                    args,
                    "next_peak",
                    "next_peak_search_level_db",
                ),
            )
        if name == "setup-sa":
            return commands.setup_sa(
                self._recording_client,
                get_test_range(_str_arg(args, "range")),
            )
        if name == "measure-fundamental":
            return commands.measure_fundamental(
                self._recording_client,
                target_freq=_float_arg(args, "target_freq"),
            )
        if name == "measure-harmonics":
            return commands.measure_harmonics(
                self._recording_client,
                fundamental=_float_arg(args, "fundamental"),
            )
        if name == "measure-inband":
            return commands.measure_inband(
                self._recording_client,
                limit=_float_arg(args, "limit"),
            )
        if name == "set-switch":
            return commands.set_switch_box(
                self._recording_client,
                input_path=InputPath(_int_arg(args, "input_path")),
                filter_path=FilterPath(_int_arg(args, "filter_path")),
            )
        if name == "rotate":
            commands.rotate_turntable(
                self._recording_client,
                angle=_float_arg(args, "angle"),
                turntable_speed=_int_arg(args, "speed", "turntable_speed"),
            )
            if _bool_arg(args, "wait", default=False):
                self._wait_for_event(
                    target="CO3000",
                    complete_command="turntable_complete",
                    timeout_s=_float_arg(args, "timeout", default=30.0),
                )
            return None
        if name == "stop-rotate":
            commands.stop_turntable(self._recording_client)
            return None
        if name == "set-reference":
            value = commands.set_reference_co3000(self._recording_client)
            if _bool_arg(args, "wait", default=False):
                self._wait_for_event(
                    target="CO3000",
                    complete_command="set_reference_complete",
                    timeout_s=_float_arg(args, "timeout", default=900.0),
                )
            return value
        if name == "self-align":
            value = commands.self_align_fsv40(self._recording_client)
            if _bool_arg(args, "wait", default=False):
                self._wait_for_event(
                    target="FSV40",
                    complete_command="self_alignment_complete",
                    timeout_s=_float_arg(args, "timeout", default=900.0),
                )
            return value
        if name in {"tdf-list", "get-tdf-list"}:
            return commands.get_tdf_list(self._recording_client)
        if name == "tdf-all-off":
            return commands.tdf_all_off(self._recording_client)
        if name == "set-tdf":
            return commands.set_tdf(
                self._recording_client,
                tdf_file_name=_str_arg(args, "file", "tdf_file_name"),
            )
        if name == "check-call":
            return commands.check_call_status(self._recording_client)
        if name == "set-ant-pol":
            return commands.set_antenna_pol(
                self._recording_client,
                pol=AntennaPol(_str_arg(args, "pol").upper()),
                input_path=InputPath(_int_arg(args, "input_path")),
            )
        if name == "raw":
            return self._raw(args)
        raise ValueError(f"unknown command: {name}")

    def _connect(self, args: dict[str, str]) -> dict[str, bool]:
        config_keys = {
            "fsv40",
            "fsv40_visa",
            "mt8000a",
            "mt8000a_visa",
            "co3000",
            "co3000_visa",
            "controller_3d",
            "controller_3d_visa",
            "switch_ip",
            "switch_port",
        }
        config = None
        if any(key in args for key in config_keys):
            config = commands.EquipmentConnectionConfig(
                fsv40_visa_resource=args.get("fsv40", args.get("fsv40_visa", "")),
                mt8000a_visa_resource=args.get(
                    "mt8000a",
                    args.get("mt8000a_visa", ""),
                ),
                co3000_visa_resource=args.get("co3000", args.get("co3000_visa", "")),
                controller_3d_visa_resource=args.get(
                    "controller_3d",
                    args.get("controller_3d_visa", ""),
                ),
                switch_box_ip_address=args.get("switch_ip", ""),
                switch_box_port=(
                    None
                    if "switch_port" not in args or not args["switch_port"].strip()
                    else int(args["switch_port"])
                ),
            )
        return commands.connect_equipment(self._recording_client, config=config)

    def _raw(self, args: dict[str, str]) -> None:
        params_text = args.get("params", "{}")
        try:
            params = json.loads(params_text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"params must be JSON object: {exc.msg}") from exc
        if not isinstance(params, dict):
            raise ValueError("params must be JSON object")
        self._recording_client.send_request(
            _str_arg(args, "target"),
            _str_arg(args, "command"),
            params,
            timeout=_float_arg(args, "timeout", default=10.0),
        )
        return None

    def _wait_for_event(
        self,
        *,
        target: str,
        complete_command: str,
        timeout_s: float,
    ) -> None:
        deadline = time.monotonic() + timeout_s
        with self._event_condition:
            start_index = len(self._event_history)

        while True:
            self._drain_events()
            with self._event_condition:
                for event in self._event_history[start_index:]:
                    if event.target != target:
                        continue
                    if event.command == complete_command:
                        self._print(
                            f"WAIT     {target} / {complete_command} completed"
                        )
                        return
                    if event.command == _COMMAND_EQUIPMENT_ERROR:
                        raise RuntimeError(
                            f"{target} / {complete_command} failed: "
                            + _json_dumps(event.params)
                        )
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"{target} / {complete_command} timeout")
                self._event_condition.wait(min(0.1, remaining))

    def _watch_events(self) -> None:
        while not self._stop_events.wait(0.1):
            self._drain_events(auto_print=self._auto_events)

    def _drain_events(self, *, auto_print: bool = True) -> None:
        pop_events = getattr(self._client, "pop_events", None)
        if pop_events is None:
            return
        events = list(pop_events(lambda _event: True))
        if not events:
            return
        with self._event_condition:
            self._event_history.extend(events)
            self._event_condition.notify_all()
        if auto_print:
            for event in events:
                self._print_event(event)

    def _print_interactions(self, start_index: int) -> None:
        for interaction in self._recording_client._interactions[start_index:]:
            self._print(f"REQUEST  {interaction.target} / {interaction.command}")
            if interaction.params:
                self._print("PARAMS   " + _json_dumps(interaction.params))
            if interaction.response is not None:
                self._print(f"STATUS   {interaction.response.status}")
                if interaction.response.result is not None:
                    self._print("RESULT   " + _json_dumps(interaction.response.result))
                if interaction.response.error is not None:
                    self._print("ERROR    " + _json_dumps(interaction.response.error))
            if interaction.error is not None:
                self._print_error(str(interaction.error))

    def _print_events(self) -> None:
        self._drain_events(auto_print=False)
        events = self.event_history
        if not events:
            self._print("No events.")
            return
        for event in events:
            self._print_event(event)

    def _print_event(self, event: Event) -> None:
        suffix = "" if not event.params else " " + _json_dumps(event.params)
        self._print(f"EVENT    {event.target} / {event.command}{suffix}")

    def _print_help(self) -> None:
        self._print(
            "\n".join(
                [
                    "Commands:",
                    "  connect [fsv40=...] [mt8000a=...] [co3000=...]",
                    "  setup-mt8000 band=78 bw=100 modulation=QPSK rb_size=135 rb_offset=67 channel=636666",
                    "  handover mid_channel=636666 band=78 bw=100 modulation=QPSK rb_size=135 rb_offset=67 channel=640000",
                    "  setup-sa-level atten=1.5 next_peak=-20",
                    "  setup-sa range=RANGE_6",
                    "  measure-fundamental target_freq=3550",
                    "  measure-harmonics fundamental=3550.25",
                    "  measure-inband limit=-30",
                    "  set-switch input_path=3 filter_path=6",
                    "  rotate angle=360 speed=4 [wait=true] [timeout=30]",
                    "  stop-rotate",
                    "  set-reference [wait=true] [timeout=900]",
                    "  self-align [wait=true] [timeout=900]",
                    "  tdf-list",
                    "  tdf-all-off",
                    "  set-tdf file=NR_Radiated.tdf",
                    "  check-call",
                    "  set-ant-pol pol=V input_path=3",
                    "  raw target=FSV40 command=\"Unknown Command\" params='{}'",
                    "  events",
                    "  quit",
                ]
            )
        )

    def _print_error(self, message: str) -> None:
        self._print(f"ERROR    {message}")

    def _print(self, message: str) -> None:
        with self._print_lock:
            print(message, file=self._output, flush=True)


def parse_line(line: str) -> tuple[str, dict[str, str]]:
    tokens = shlex.split(line.strip())
    if not tokens:
        return "", {}
    name = tokens[0]
    args: dict[str, str] = {}
    for token in tokens[1:]:
        if "=" not in token:
            raise ValueError(f"expected key=value argument: {token}")
        key, value = token.split("=", 1)
        if not key:
            raise ValueError(f"expected key=value argument: {token}")
        args[key.replace("-", "_")] = value
    return name, args


def _str_arg(args: dict[str, str], *names: str, default: str | None = None) -> str:
    for name in names:
        if name in args:
            return args[name]
    if default is not None:
        return default
    raise ValueError(f"missing argument: {names[0]}")


def _int_arg(args: dict[str, str], *names: str, default: int | None = None) -> int:
    value = _str_arg(
        args,
        *names,
        default=None if default is None else str(default),
    )
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{names[0]} must be int") from exc


def _float_arg(
    args: dict[str, str],
    *names: str,
    default: float | None = None,
) -> float:
    value = _str_arg(
        args,
        *names,
        default=None if default is None else str(default),
    )
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{names[0]} must be number") from exc


def _bool_arg(args: dict[str, str], name: str, *, default: bool) -> bool:
    if name not in args:
        return default
    value = args[name].strip().lower()
    if value in {"1", "true", "yes", "y", "on"}:
        return True
    if value in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"{name} must be bool")


def _modulation_arg(args: dict[str, str], name: str) -> Modulation | str:
    value = _str_arg(args, name)
    normalized = value.strip().upper().replace("-", "_")
    if normalized == "QPSK":
        return Modulation.QPSK
    if normalized in {"PI_OVER_2_BPSK", "PI/2_BPSK", "PI/2 BPSK"}:
        return Modulation.PI_OVER_2_BPSK
    return value


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Persistent mock LV client console")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5025)
    parser.add_argument("--no-auto-events", action="store_true")
    args = parser.parse_args(argv)

    client = TcpClient()
    console = MockLvClientConsole(client, auto_events=not args.no_auto_events)

    try:
        client.connect_to(args.host, args.port)
        print(f"Connected to {args.host}:{args.port}")
        console.start_event_watcher()
        console.run()
        return 0
    except Exception as exc:
        print(f"ERROR    {exc}", file=sys.stderr)
        return 1
    finally:
        console.stop_event_watcher()
        client.disconnect_from_host()


if __name__ == "__main__":
    raise SystemExit(main())
