import streamlit as st
import anthropic
import os

# Load secrets
API_KEY = st.secrets["claude"]["api_token"]
MCP_URL = st.secrets["pipeboard"]["url"]
os.environ["PIPEBOARD_API_TOKEN"] = st.secrets["pipeboard"]["api_token"]

# Initialize client
client = anthropic.Anthropic(api_key=API_KEY)

# Setup UI
st.set_page_config(page_title="Meta Ads Chat", layout="centered")
st.title("📊 Meta Ads Assistant")
st.write("Ask me anything about your Meta Ads performance.")

# Initialize persistent chat history
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []  # [{ "user": str, "claude_blocks": list, "text": str }]

# Show chat history
for turn in st.session_state.chat_history:
    with st.chat_message("user"):
        st.markdown(turn["user"])
    with st.chat_message("assistant"):
        # st.markdown(turn["text"])
        for block in turn["claude_blocks"]:
            if getattr(block, "type", "") == "mcp_tool_use":
                with st.expander(f"⚙️ Tool Called: `{block.name}`"):
                    st.markdown("**Input:**")
                    st.json(block.input)
            elif hasattr(block, "content"):
                with st.expander("🔧 Tool Result"):
                    for sub_block in block.content:
                        if hasattr(sub_block, "text"):
                            st.markdown(sub_block.text)

# New user input
if user_input := st.chat_input("Ask a question about your meta ads..."):
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        text_container = st.empty()
        streamed_text = ""
        tool_blocks = []

        try:
            with client.messages.stream(
                model="claude-sonnet-4-20250514",
                max_tokens=200000,
                messages=[{"role": "user", "content": user_input}],
                mcp_servers=[{
                    "type": "url",
                    "url": f"{MCP_URL}/mcp/",
                    "name": "meta-ads"
                }],
                extra_headers={"anthropic-beta": "mcp-client-2025-04-04"}
            ) as stream:
                for text in stream.text_stream:
                    streamed_text += text
                    text_container.markdown(streamed_text)

                # Once streaming ends, store blocks (tool calls/results)
                for block in stream.get_final_message().content:
                    if getattr(block, "type", "") in ["mcp_tool_use", "mcp_tool_result"]:
                        tool_blocks.append(block)
                        if block.type == "mcp_tool_use":
                            with st.expander(f"⚙️ Tool Called: `{block.name}`"):
                                st.markdown("**Input:**")
                                st.json(block.input)
                        elif hasattr(block, "content"):
                            with st.expander("🔧 Tool Result"):
                                for sub_block in block.content:
                                    if hasattr(sub_block, "text"):
                                        st.markdown(sub_block.text)

        except Exception as e:
            st.error(f"❌ Error: {e}")

        # Save to session history
        st.session_state.chat_history.append({
            "user": user_input,
            "text": streamed_text,
            "claude_blocks": tool_blocks
        })
