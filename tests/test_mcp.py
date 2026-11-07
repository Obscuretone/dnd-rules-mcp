import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def exercise_server():
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "dnd_rules_mcp.cli", "serve"]
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert {t.name for t in tools.tools} == {"search_rules", "get_rule", "can_i_do"}
            assert all(t.annotations.readOnlyHint for t in tools.tools)
            search = await session.call_tool(
                "search_rules", {"query": "Fireball", "mode": "fts", "kind": "spell", "limit": 1}
            )
            assert not search.isError
            assert search.structuredContent["results"][0]["id"] == "spell-fireball"
            rule = await session.call_tool("get_rule", {"rule_id": "spell-fireball"})
            assert "8d6 Fire damage" in rule.structuredContent["text"]
            facts = json.loads((Path(__file__).parents[1] / "examples/fireball.json").read_text())
            facts["slot_already_expended_this_turn"] = True
            review = await session.call_tool(
                "can_i_do",
                {
                    "question": "Can I cast Fireball after spending a spell slot this turn?",
                    "facts": facts,
                    "mode": "fts",
                },
            )
            assert not review.isError
            assert review.structuredContent["check"]["verdict"] == "disallowed"
            assert any(
                f["code"] == "one_slot_per_turn"
                for f in review.structuredContent["check"]["findings"]
            )
            freeform = await session.call_tool(
                "can_i_do", {"question": "How does a Bag of Holding work?", "mode": "fts"}
            )
            assert freeform.structuredContent["check"]["verdict"] == "requires_interpretation"
            source = await session.read_resource("srd://source")
            assert json.loads(source.contents[0].text)["pages"] == 364
            page = await session.read_resource("srd://page/105")
            assert (
                "One Spell with a Spell Slot per Turn" in json.loads(page.contents[0].text)["text"]
            )
            prompts = await session.list_prompts()
            assert "adjudicate" in {p.name for p in prompts.prompts}
            prompt = await session.get_prompt("adjudicate", {"question": "Can I move while Prone?"})
            assert "Can I move while Prone?" in prompt.messages[0].content.text
            invalid = await session.call_tool(
                "can_i_do", {"question": "Move?", "facts": {"kind": "movement", "distance_ft": -1}}
            )
            assert invalid.isError


def test_real_stdio_mcp_roundtrip():
    asyncio.run(exercise_server())
