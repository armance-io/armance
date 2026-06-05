from __future__ import annotations


class TestBoostTagSandbox:
    def test_specialist_may_emit_boost_request(self) -> None:
        from armance.service.agent_sandbox import scrub_reply
        out = scrub_reply("ok [EXECUTE:/boost-request]", agent_role="specialist")
        assert "[EXECUTE:/boost-request]" in out

    def test_specialist_may_emit_boost_release(self) -> None:
        from armance.service.agent_sandbox import scrub_reply
        out = scrub_reply("done [EXECUTE:/boost-release]", agent_role="specialist")
        assert "[EXECUTE:/boost-release]" in out

    def test_malik_may_not_emit_boost_request(self) -> None:
        from armance.service.agent_sandbox import scrub_reply
        out = scrub_reply("[EXECUTE:/boost-request]", agent_role="malik")
        assert "[EXECUTE:/boost-request]" not in out
