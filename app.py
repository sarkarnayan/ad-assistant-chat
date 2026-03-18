import asyncio
import html
import json
import os
from typing import Any

import streamlit as st
from fastmcp import Client as MCPClient
from openai import OpenAI


def get_secret_value(section_name, field_name, env_var=None, default=None):
    if env_var:
        env_value = os.getenv(env_var)
        if env_value:
            return env_value

    section = st.secrets.get(section_name, {})
    return section.get(field_name, default)


DEEPINFRA_API_KEY = get_secret_value(
    "deepinfra",
    "api_token",
    env_var="DEEPINFRA_API_TOKEN",
)
PIPEBOARD_API_TOKEN = get_secret_value(
    "pipeboard",
    "api_token",
    env_var="PIPEBOARD_API_TOKEN",
)
MCP_BASE_URL = get_secret_value(
    "pipeboard",
    "url",
    env_var="PIPEBOARD_URL",
    default="https://meta-ads.mcp.pipeboard.co",
)
MODEL_NAME = get_secret_value(
    "deepinfra",
    "model",
    env_var="DEEPINFRA_MODEL",
    default="nvidia/NVIDIA-Nemotron-3-Super-120B-A12B",
)
MAX_TOKENS = int(
    get_secret_value(
        "deepinfra",
        "max_tokens",
        env_var="DEEPINFRA_MAX_TOKENS",
        default=4096,
    )
)

SYSTEM_PROMPT = """\
You are an expert Meta Ads analyst and campaign manager. You have access to a
full suite of Meta Ads tools via the Pipeboard MCP server. Use them proactively
whenever the user asks about ad performance, campaigns, budgets, audiences, or
creatives.

Available tool categories and when to use them:

ACCOUNT MANAGEMENT
- get_ad_accounts        — list all accessible ad accounts
- get_account_info       — details for a specific account (spend limits, status)
- get_account_pages      — Facebook pages linked to an account

CAMPAIGNS
- get_campaigns          — list campaigns; use status/objective filters to narrow
- get_campaign_details   — full details for one campaign
- create_campaign        — create a new campaign (start paused to review first)
- update_campaign        — change name, budget, status, objective
- create_budget_schedule — schedule budget spikes for high-demand periods

AD SETS
- get_adsets             — list ad sets, optionally filtered by campaign
- get_adset_details      — full targeting, budget, and optimisation details
- create_adset           — create an ad set with targeting and bid strategy
- update_adset           — update targeting, frequency caps, budgets

ADS
- get_ads                — list ads, optionally filtered by campaign or ad set
- get_ad_details         — full details for one ad
- create_ad              — attach an existing creative to an ad set
- update_ad              — change status, bid amount, or creative

CREATIVES & MEDIA
- get_ad_creatives       — retrieve creative details for an ad
- upload_ad_image        — upload an image; returns hash to use in creatives
- create_ad_creative     — build a creative (image + headline + body + CTA)
- update_ad_creative     — edit copy, headline, or CTA on an existing creative
- get_ad_image           — download and display an ad image

ANALYTICS & INSIGHTS
- get_insights           — performance metrics (impressions, clicks, spend, CTR,
                           CPC, CPM, reach, conversions) for a campaign/ad set/ad;
                           supports time ranges: today, yesterday, last_7d,
                           last_14d, last_30d, this_month, last_month;
                           supports breakdowns: age, gender, platform, placement,
                           region, country, device, publisher_platform
- bulk_get_insights      — same metrics across ALL accounts in one call
                           (uses smart caching; takes 3-5 s on first call)

AUDIENCE TARGETING
- search_interests        — find interest targeting options by keyword
- get_interest_suggestions — related interests for existing ones
- estimate_audience_size  — estimate reach before launching
- search_behaviors        — find behaviour targeting options
- search_demographics     — life events, income levels, and other demographics
- search_geo_locations    — countries, regions, cities, zip codes

PREMIUM TOOLS (available if the account has a paid Pipeboard plan)
- duplicate_campaign     — clone a campaign with all ad sets and ads
- duplicate_adset        — clone an ad set, optionally with targeting changes
- duplicate_ad           — clone an ad to a different ad set
- duplicate_creative     — clone a creative with copy variations

Guidelines:
- Always fetch real data with tools before answering performance questions.
- When creating anything (campaign, ad set, ad), start with paused status.
- Use get_insights with appropriate time ranges and breakdowns for analysis.
- For bulk cross-account comparisons, prefer bulk_get_insights.
- Keep API calls efficient: use filters rather than fetching all records.
"""

if PIPEBOARD_API_TOKEN:
    os.environ["PIPEBOARD_API_TOKEN"] = PIPEBOARD_API_TOKEN

if not DEEPINFRA_API_KEY:
    st.error(
        "Missing DeepInfra API token. Set deepinfra.api_token in Streamlit "
        "secrets or DEEPINFRA_API_TOKEN."
    )
    st.stop()

if not MCP_BASE_URL:
    MCP_BASE_URL = "https://meta-ads.mcp.pipeboard.co"

client = OpenAI(
    base_url="https://api.deepinfra.com/v1/openai",
    api_key=DEEPINFRA_API_KEY,
)


def mcp_endpoint_url():
    url = MCP_BASE_URL.rstrip("/")
    # Only add a trailing slash when there is no query string,
    # to avoid corrupting ?token=... style URLs.
    if "?" not in url:
        url += "/"
    return url


def copy_button_js(text, key="copy"):
    escaped = html.escape(text).replace("`", "\\`")
    return f"""
    <button id="{key}"
    onclick="navigator.clipboard.writeText(`{escaped}`); alert('Copied')"
    style='margin-top: 4px; padding: 4px 8px; font-size: 0.85rem;'>
    Copy
    </button>
    """


def run_async(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


def extract_text_parts(content: Any) -> list[str]:
    text_parts = []
    for block in content or []:
        text = getattr(block, "text", None)
        if text:
            text_parts.append(str(text))
    return text_parts


def serialize_blocks(content: Any) -> list[Any]:
    serialized = []
    for block in content or []:
        if hasattr(block, "model_dump"):
            serialized.append(block.model_dump(mode="json"))
        else:
            serialized.append(str(block))
    return serialized


def tool_result_to_text(result: Any) -> str:
    structured_content = getattr(result, "structured_content", None)
    if structured_content is not None:
        return json.dumps(
            structured_content,
            ensure_ascii=True,
            default=str,
        )

    data = getattr(result, "data", None)
    if data is not None:
        if isinstance(data, (dict, list)):
            return json.dumps(data, ensure_ascii=True, default=str)
        return str(data)

    text_parts = extract_text_parts(getattr(result, "content", None))
    if text_parts:
        return "\n\n".join(text_parts)

    return json.dumps(
        serialize_blocks(getattr(result, "content", None)),
        ensure_ascii=True,
        default=str,
    )


def tool_result_for_display(result: Any):
    structured_content = getattr(result, "structured_content", None)
    if structured_content is not None:
        return structured_content

    data = getattr(result, "data", None)
    if data is not None:
        if isinstance(data, (dict, list, str, int, float, bool)):
            return data
        return str(data)

    text_parts = extract_text_parts(getattr(result, "content", None))
    if text_parts:
        return "\n\n".join(text_parts)

    return serialize_blocks(getattr(result, "content", None))


def render_tool_output(output):
    if isinstance(output, (dict, list)):
        st.json(output)
    elif output is None:
        st.write("No output")
    else:
        st.markdown(str(output))


def render_tool_calls(tool_calls):
    for tool_call in tool_calls:
        with st.expander(
            f"Tool Called: {tool_call['name']}",
            expanded=False,
        ):
            st.markdown("Input")
            st.json(tool_call["arguments"])
            st.markdown("Output")
            render_tool_output(tool_call["result"])


def render_history_entry(entry, index):
    with st.chat_message("user"):
        st.markdown(entry["user"])
        st.markdown(
            copy_button_js(entry["user"], f"user_copy_{index}"),
            unsafe_allow_html=True,
        )

    with st.chat_message("assistant"):
        if entry.get("assistant"):
            st.markdown(entry["assistant"])
            st.markdown(
                copy_button_js(
                    entry["assistant"],
                    f"assistant_copy_{index}",
                ),
                unsafe_allow_html=True,
            )

        if entry.get("tool_calls"):
            render_tool_calls(entry["tool_calls"])


def build_openai_tools(mcp_tools):
    openai_tools = []
    for mcp_tool in mcp_tools:
        parameters = mcp_tool.inputSchema or {
            "type": "object",
            "properties": {},
        }
        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": mcp_tool.name,
                    "description": mcp_tool.description
                    or f"Call the {mcp_tool.name} tool.",
                    "parameters": parameters,
                },
            }
        )
    return openai_tools


def get_function_tool_call(tool_call: Any):
    function = getattr(tool_call, "function", None)
    if function is None:
        raise RuntimeError("DeepInfra returned a non-function tool call.")
    return function


async def run_deepinfra_turn(user_input):
    async with MCPClient(
        mcp_endpoint_url(),
        auth=PIPEBOARD_API_TOKEN,
    ) as mcp_client:
        mcp_tools = await mcp_client.list_tools()
        tool_schemas = build_openai_tools(mcp_tools)
        mcp_instructions = getattr(
            mcp_client.initialize_result,
            "instructions",
            None,
        )

        # Build system prompt: our domain prompt + any server-provided instructions.
        system_content = SYSTEM_PROMPT
        if mcp_instructions:
            system_content = system_content + "\n\n" + mcp_instructions

        messages: list[Any] = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_input},
        ]

        first_response = client.chat.completions.create(
            model=MODEL_NAME,
            max_tokens=MAX_TOKENS,
            messages=messages,
            tools=tool_schemas,
            tool_choice="auto",
        )
        assistant_message = first_response.choices[0].message
        tool_events = []

        if assistant_message.tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": assistant_message.content or "",
                    "tool_calls": [
                        tool_call.model_dump()
                        for tool_call in assistant_message.tool_calls
                    ],
                }
            )

            for tool_call in assistant_message.tool_calls:
                function_call = get_function_tool_call(tool_call)
                arguments = json.loads(function_call.arguments or "{}")
                tool_result = await mcp_client.call_tool(
                    function_call.name,
                    arguments,
                    raise_on_error=False,
                )
                tool_text = tool_result_to_text(tool_result)
                tool_events.append(
                    {
                        "name": function_call.name,
                        "arguments": arguments,
                        "result": tool_result_for_display(tool_result),
                        "is_error": tool_result.is_error,
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_text,
                    }
                )

            final_response = client.chat.completions.create(
                model=MODEL_NAME,
                max_tokens=MAX_TOKENS,
                messages=messages,
                tools=tool_schemas,
                tool_choice="auto",
            )
            final_message = final_response.choices[0].message
            if final_message.tool_calls:
                raise RuntimeError(
                    "DeepInfra returned nested tool calls. The current "
                    "integration supports one tool round per response."
                )
            return final_message.content or "", tool_events

        return assistant_message.content or "", tool_events


st.set_page_config(page_title="Meta Ads Chat", layout="centered")
st.title("Meta Ads Assistant")
st.write("Ask me anything about your Meta Ads performance.")
st.caption(f"Model: {MODEL_NAME}")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

for idx, entry in enumerate(st.session_state.chat_history):
    if "claude_blocks" in entry:
        continue
    render_history_entry(entry, idx)

if user_input := st.chat_input("Ask a question..."):
    with st.chat_message("user"):
        st.markdown(user_input)
        st.markdown(
            copy_button_js(user_input, "live_user_copy"),
            unsafe_allow_html=True,
        )

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                assistant_text, tool_calls = run_async(
                    run_deepinfra_turn(user_input)
                )

                if assistant_text:
                    st.markdown(assistant_text)
                    st.markdown(
                        copy_button_js(
                            assistant_text,
                            "live_assistant_copy",
                        ),
                        unsafe_allow_html=True,
                    )

                if tool_calls:
                    render_tool_calls(tool_calls)

                st.session_state.chat_history.append(
                    {
                        "user": user_input,
                        "assistant": assistant_text,
                        "tool_calls": tool_calls,
                    }
                )
            except Exception as exc:
                st.error(f"Error: {exc}")
