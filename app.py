import asyncio
from decimal import Decimal
import json
import os
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

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


def get_bool_secret(section_name, field_name, env_var=None, default=False):
    value = get_secret_value(
        section_name,
        field_name,
        env_var=env_var,
        default=default,
    )
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def get_decimal_secret(section_name, field_name, env_var=None, default="0"):
    value = get_secret_value(
        section_name,
        field_name,
        env_var=env_var,
        default=default,
    )
    return Decimal(str(value))


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
MAX_TOOL_ROUNDS = int(
    get_secret_value(
        "deepinfra",
        "max_tool_rounds",
        env_var="DEEPINFRA_MAX_TOOL_ROUNDS",
        default=6,
    )
)
SHOW_TOOL_CALLS = get_bool_secret(
    "ui",
    "show_tool_calls",
    env_var="SHOW_TOOL_CALLS",
    default=False,
)
SHOW_QUERY_COST = get_bool_secret(
    "ui",
    "show_query_cost",
    env_var="SHOW_QUERY_COST",
    default=True,
)
INPUT_COST_PER_MILLION = get_decimal_secret(
    "deepinfra",
    "input_cost_per_million",
    env_var="DEEPINFRA_INPUT_COST_PER_MILLION",
    default="1.20",
)
OUTPUT_COST_PER_MILLION = get_decimal_secret(
    "deepinfra",
    "output_cost_per_million",
    env_var="DEEPINFRA_OUTPUT_COST_PER_MILLION",
    default="6.00",
)
CACHED_INPUT_COST_PER_MILLION = get_decimal_secret(
    "deepinfra",
    "cached_input_cost_per_million",
    env_var="DEEPINFRA_CACHED_INPUT_COST_PER_MILLION",
    default="0.24",
)


def resolve_pipeboard_connection(url: str, api_token: str | None):
    parsed_url = urlparse(url)
    query = parse_qs(parsed_url.query, keep_blank_values=True)

    token_from_query = None
    if "token" in query and query["token"]:
        token_from_query = query["token"][0]

    effective_token = api_token or token_from_query

    if "token" in query:
        query.pop("token")

    clean_query = urlencode(query, doseq=True)
    normalized_path = parsed_url.path or "/"
    # The open-source onrender deployment serves MCP at /mcp/.
    if parsed_url.netloc.endswith("onrender.com") and normalized_path in ("", "/"):
        normalized_path = "/mcp/"

    normalized_url = urlunparse(
        (
            parsed_url.scheme,
            parsed_url.netloc,
            normalized_path,
            parsed_url.params,
            clean_query,
            parsed_url.fragment,
        )
    )

    return normalized_url, effective_token


MCP_ENDPOINT_URL, PIPEBOARD_AUTH_TOKEN = resolve_pipeboard_connection(
    MCP_BASE_URL,
    PIPEBOARD_API_TOKEN,
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

if PIPEBOARD_AUTH_TOKEN:
    os.environ["PIPEBOARD_API_TOKEN"] = PIPEBOARD_AUTH_TOKEN

if not DEEPINFRA_API_KEY:
    st.error(
        "Missing DeepInfra API token. Set deepinfra.api_token in Streamlit "
        "secrets or DEEPINFRA_API_TOKEN."
    )
    st.stop()

if not MCP_ENDPOINT_URL:
    MCP_ENDPOINT_URL = "https://meta-ads.mcp.pipeboard.co/"

if not PIPEBOARD_AUTH_TOKEN:
    st.error(
        "Missing Pipeboard API token. Set pipeboard.api_token or include "
        "?token=... in pipeboard.url."
    )
    st.stop()

if "onrender.com" in MCP_ENDPOINT_URL:
    st.warning(
        "Pipeboard URL points to an onrender host. For Pipeboard remote MCP, "
        "use https://meta-ads.mcp.pipeboard.co/"
    )

client = OpenAI(
    base_url="https://api.deepinfra.com/v1/openai",
    api_key=DEEPINFRA_API_KEY,
)


def mcp_endpoint_url():
    return MCP_ENDPOINT_URL


def run_async(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError as exc:
        if "asyncio.run() cannot be called from a running event loop" not in str(
            exc
        ):
            raise
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


def empty_usage_totals():
    return {
        "prompt_tokens": 0,
        "cached_prompt_tokens": 0,
        "non_cached_prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }


def add_response_usage(usage_totals, response):
    usage = getattr(response, "usage", None)
    if usage is None:
        return

    prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    total_tokens = int(getattr(usage, "total_tokens", 0) or 0)

    prompt_details = getattr(usage, "prompt_tokens_details", None)
    cached_prompt_tokens = int(
        getattr(prompt_details, "cached_tokens", 0) or 0
    )
    cached_prompt_tokens = max(0, min(cached_prompt_tokens, prompt_tokens))
    non_cached_prompt_tokens = prompt_tokens - cached_prompt_tokens

    usage_totals["prompt_tokens"] += prompt_tokens
    usage_totals["cached_prompt_tokens"] += cached_prompt_tokens
    usage_totals["non_cached_prompt_tokens"] += non_cached_prompt_tokens
    usage_totals["completion_tokens"] += completion_tokens
    usage_totals["total_tokens"] += total_tokens


def build_cost_summary(usage_totals):
    if usage_totals["total_tokens"] <= 0:
        return None

    input_cost = (
        Decimal(usage_totals["non_cached_prompt_tokens"])
        * INPUT_COST_PER_MILLION
        / Decimal(1_000_000)
    )
    cached_input_cost = (
        Decimal(usage_totals["cached_prompt_tokens"])
        * CACHED_INPUT_COST_PER_MILLION
        / Decimal(1_000_000)
    )
    output_cost = (
        Decimal(usage_totals["completion_tokens"])
        * OUTPUT_COST_PER_MILLION
        / Decimal(1_000_000)
    )
    total_cost = input_cost + cached_input_cost + output_cost

    return {
        **usage_totals,
        "input_cost": float(input_cost),
        "cached_input_cost": float(cached_input_cost),
        "output_cost": float(output_cost),
        "total_cost": float(total_cost),
    }


def format_cost_summary(cost_summary):
    return f"Cost: ${cost_summary['total_cost']:.6f}"


def render_history_entry(entry, index):
    with st.chat_message("user"):
        st.markdown(entry["user"])

    with st.chat_message("assistant"):
        if entry.get("assistant"):
            st.markdown(entry["assistant"])

        if SHOW_QUERY_COST and entry.get("cost_summary"):
            st.caption(format_cost_summary(entry["cost_summary"]))

        if SHOW_TOOL_CALLS and entry.get("tool_calls"):
            render_tool_calls(entry["tool_calls"])


def build_memory_messages(chat_history, max_turns=2):
    recent_entries = []
    for entry in reversed(chat_history):
        if "claude_blocks" in entry:
            continue
        if not entry.get("user"):
            continue
        recent_entries.append(entry)
        if len(recent_entries) >= max_turns:
            break

    memory_messages = []
    for entry in reversed(recent_entries):
        memory_messages.append(
            {
                "role": "user",
                "content": entry["user"],
            }
        )
        if entry.get("assistant"):
            memory_messages.append(
                {
                    "role": "assistant",
                    "content": entry["assistant"],
                }
            )

    return memory_messages


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


async def run_deepinfra_turn(user_input, chat_history):
    async with MCPClient(
        mcp_endpoint_url(),
        auth=PIPEBOARD_AUTH_TOKEN,
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

        memory_messages = build_memory_messages(chat_history, max_turns=2)
        messages: list[Any] = [
            {"role": "system", "content": system_content},
            *memory_messages,
            {"role": "user", "content": user_input},
        ]
        tool_events = []
        usage_totals = empty_usage_totals()
        latest_assistant_text = ""

        for _ in range(MAX_TOOL_ROUNDS):
            response = client.chat.completions.create(
                model=MODEL_NAME,
                max_tokens=MAX_TOKENS,
                messages=messages,
                tools=tool_schemas,
                tool_choice="auto",
            )
            add_response_usage(usage_totals, response)
            assistant_message = response.choices[0].message
            latest_assistant_text = assistant_message.content or ""
            tool_calls = assistant_message.tool_calls or []

            if not tool_calls:
                return (
                    latest_assistant_text,
                    tool_events,
                    build_cost_summary(usage_totals),
                )

            messages.append(
                {
                    "role": "assistant",
                    "content": latest_assistant_text,
                    "tool_calls": [
                        tool_call.model_dump() for tool_call in tool_calls
                    ],
                }
            )

            for tool_call in tool_calls:
                function_call = get_function_tool_call(tool_call)
                raw_arguments = function_call.arguments or "{}"
                try:
                    arguments = json.loads(raw_arguments)
                except json.JSONDecodeError:
                    arguments = {}

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

        fallback_text = (
            latest_assistant_text
            or "I completed multiple tool rounds but still need additional "
            "tool calls to finish this request."
        )
        return fallback_text, tool_events, build_cost_summary(usage_totals)


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

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                assistant_text, tool_calls, cost_summary = run_async(
                    run_deepinfra_turn(
                        user_input,
                        st.session_state.chat_history,
                    )
                )

                if assistant_text:
                    st.markdown(assistant_text)

                if SHOW_QUERY_COST and cost_summary:
                    st.caption(format_cost_summary(cost_summary))

                if SHOW_TOOL_CALLS and tool_calls:
                    render_tool_calls(tool_calls)

                new_entry = {
                    "user": user_input,
                    "assistant": assistant_text,
                    "tool_calls": tool_calls,
                    "cost_summary": cost_summary,
                }
                last_entry = (
                    st.session_state.chat_history[-1]
                    if st.session_state.chat_history
                    else None
                )
                if not last_entry or last_entry != new_entry:
                    st.session_state.chat_history.append(new_entry)
            except Exception as exc:
                error_text = str(exc)
                if "401" in error_text and "pipeboard" in error_text.lower():
                    st.error(
                        "Pipeboard authentication failed (401). Regenerate your "
                        "token at https://pipeboard.co/api-tokens or set "
                        "pipeboard.api_token in secrets."
                    )
                else:
                    st.error(f"Error: {exc}")
