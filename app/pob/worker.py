"""PoB 계산 워커 프로세스.

GUI 가 `<exe> --pob-worker <port>` 로 실행한다. 127.0.0.1:<port> 로 접속해
한 줄짜리 JSON 요청/응답을 주고받는다. 소켓이 끊기면 종료.
"""
from __future__ import annotations

import json
import socket
import sys
import time
import traceback
from pathlib import Path


def run(port: int, log_path: Path) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logf = open(log_path, "w", encoding="utf-8")

    def log(msg: str) -> None:
        logf.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
        logf.flush()

    sock = socket.create_connection(("127.0.0.1", port))
    rf = sock.makefile("rb")
    wf = sock.makefile("wb")
    engine = None

    def send(obj: dict) -> None:
        wf.write(json.dumps(obj, ensure_ascii=False).encode("utf-8") + b"\n")
        wf.flush()

    log(f"worker started, port {port}")
    for raw in rf:
        try:
            req = json.loads(raw)
        except ValueError:
            continue
        rid, cmd, args = req.get("id"), req.get("cmd"), req.get("args") or {}
        t0 = time.perf_counter()
        try:
            if cmd == "init":
                from pob.engine import PobEngine

                engine = PobEngine(Path(args["src"]), Path(args["user"]), log=log)
                engine.g.es_minion_in_main = bool(args.get("minion_in_main", True))
                result = {"ok": True}
            elif cmd == "set_ascend" and engine is not None:
                result = {"summary": engine.set_ascend(bool(args.get("on"))), "xml": engine.save_xml()}
            elif cmd in ("set_minion", "set_minion_skill") and engine is not None:
                fn = engine.set_minion if cmd == "set_minion" else engine.set_minion_skill
                result = {"summary": fn(int(args["index"])), "xml": engine.save_xml()}
            elif cmd == "set_minion_in_main" and engine is not None:
                result = {"summary": engine.set_minion_in_main(args.get("on", True)), "xml": engine.save_xml()}
            elif engine is None:
                raise RuntimeError("engine not initialised")
            elif cmd == "load_xml":
                result = {"summary": engine.load_xml(args["xml"], args.get("name", ""))}
                if "vaal_on" in args and engine.vaal_defaults(args["vaal_on"]):
                    result["summary"] = engine.summary()
                result["xml"] = engine.save_xml()
            elif cmd == "load_character":
                result = {"summary": engine.load_character_json(args["json"], args.get("prev_xml"))}
                if "vaal_on" in args and engine.vaal_defaults(args["vaal_on"]):
                    result["summary"] = engine.summary()
                result["xml"] = engine.save_xml()
            elif cmd == "set_main_group":
                result = {"summary": engine.set_main_group(int(args["index"])), "xml": engine.save_xml()}
            elif cmd == "set_group":
                result = {
                    "summary": engine.set_group(int(args["index"]), args.get("enabled"), args.get("full_dps")),
                    "xml": engine.save_xml(),
                }
            elif cmd in ("set_config", "reset_config", "set_flask", "set_active_skill", "set_skill_part", "set_skill_knob",
                         "set_level"):
                fn = {
                    "set_config": lambda: engine.set_config(args["var"], args.get("value")),
                    "reset_config": engine.reset_config,
                    "set_flask": lambda: engine.set_flask(args["slot"], args["active"]),
                    "set_active_skill": lambda: engine.set_active_skill(int(args["group"]), int(args["active"])),
                    "set_skill_part": lambda: engine.set_skill_part(int(args["part"])),
                    "set_level": lambda: engine.set_level(int(args["level"])),
                    "set_skill_knob": lambda: engine.set_skill_knob(args["group"], args["active"], args["key"],
                                                                    args.get("value")),
                }[cmd]
                result = {"summary": fn(), "xml": engine.save_xml()}
            elif cmd == "equipment":
                result = engine.equipment()
            elif cmd == "equipment_impact":
                result = engine.equipment_impact(args.get("skip") or 0, args.get("limit"))
            elif cmd == "set_slot":
                r = engine.set_slot(args["slot"], args.get("item") or 0) or {}
                if r.get("error"):
                    raise RuntimeError(r["error"])
                result = {"summary": engine.summary(), "xml": engine.save_xml()}
            elif cmd == "set_gem":
                r = engine.set_gem(args["group"], args["gem"], args.get("level"), args.get("quality"), args.get("enabled"),
                                    args.get("side")) or {}
                if r.get("error"):
                    raise RuntimeError(r["error"])
                result = {"summary": engine.summary(), "xml": engine.save_xml()}
            elif cmd == "optimize":
                result = engine.optimize(args.get("spec") or {})
                if result.get("error"):
                    raise RuntimeError(result["error"])
            elif cmd == "gem_impact":
                result = engine.gem_impact(args.get("skip") or 0, args.get("limit"))
            elif cmd == "flasks":
                result = engine.flasks()
            elif cmd == "item_catalog":
                result = engine.item_catalog(args["slot"])
            elif cmd in ("draft_new", "draft_edit"):
                result = (engine.draft_new if cmd == "draft_new" else engine.draft_edit)(args.get("spec") or {})
                if result.get("error"):
                    raise RuntimeError(result["error"])
            elif cmd in ("draft_equip", "draft_replace"):
                r = (engine.draft_equip if cmd == "draft_equip" else engine.draft_replace)(args["slot"]) or {}
                if r.get("error"):
                    raise RuntimeError(r["error"])
                result = {"summary": engine.summary(), "xml": engine.save_xml()}
            elif cmd == "tree_layout":
                result = {"layout": engine.tree_layout(), "state": engine.tree_state()}
            elif cmd == "tree_state":
                result = {"state": engine.tree_state()}
            elif cmd == "tree_preview":
                result = engine.tree_preview(args["id"])
            elif cmd == "tree_mastery_preview":
                result = engine.tree_mastery_preview(args["id"])
            elif cmd in ("tree_click", "tree_restore", "tree_reset", "tree_import_url"):
                r = {
                    "tree_click": lambda: engine.tree_click(args["id"], args.get("effect")),
                    "tree_restore": lambda: engine.tree_restore(args["snap"]),
                    "tree_reset": engine.tree_reset,
                    "tree_import_url": lambda: engine.tree_import_url(args["url"]),
                }[cmd]() or {}
                if r.get("error"):
                    raise RuntimeError(r["error"])
                result = {"summary": engine.summary(), "xml": engine.save_xml(), "state": engine.tree_state()}
            elif cmd == "compare":
                result = engine.compare_item(args["text"], args.get("nodef"))
            elif cmd == "explain":
                result = engine.explain_item(args["text"], args["slot"])
            elif cmd == "slot_variant":
                result = engine.slot_variant(args["slot"], args.get("off") or [], args.get("contrib", False),
                                             args.get("nodef"))
            elif cmd == "summary":
                result = {"summary": engine.summary()}
            else:
                raise RuntimeError(f"unknown command {cmd}")
            log(f"{cmd} ok {time.perf_counter() - t0:.2f}s")
            send({"id": rid, "ok": True, "result": result})
        except Exception as e:  # noqa: BLE001
            log(f"{cmd} failed: {traceback.format_exc()}")
            send({"id": rid, "ok": False, "error": str(e).splitlines()[0][:500] if str(e) else type(e).__name__})
    log("socket closed, exit")
    return 0


if __name__ == "__main__":
    sys.exit(run(int(sys.argv[1]), Path(sys.argv[2])))
