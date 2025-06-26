import streamlit as st
import anthropic
import os

# Load secrets
API_KEY = st.secrets["claude"]["api_token"]
MCP_URL = st.secrets["pipeboard"]["url"]
os.environ["PIPEBOARD_API_TOKEN"] = st.secrets["pipeboard"]["api_token"]

# Initialize Claude client
client = anthropic.Anthropic(api_key=API_KEY)

# Page config
st.set_page_config(page_title="Meta Ads Chat", layout="centered")
st.title("📊 Meta Ads Assistant")
st.write("Ask me anything about your Meta Ads performance.")

# Initialize chat history
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []  # list of { "user": str, "claude_blocks": list }

# Display full chat history
for entry in st.session_state.chat_history:
    with st.chat_message("user"):
        st.markdown(entry["user"])

    with st.chat_message("assistant"):
        for block in entry["claude_blocks"]:
            if hasattr(block, "text"):
                st.markdown(block.text)

            elif hasattr(block, "content"):
                with st.expander("🔧 Tool Result", expanded=False):
                    for sub_block in block.content:
                        if hasattr(sub_block, "text"):
                            st.markdown(sub_block.text)

            elif getattr(block, "type", "") == "mcp_tool_use":
                with st.expander(f"⚙️ Tool Called: `{block.name}`", expanded=False):
                    st.markdown("**Input:**")
                    st.json(block.input)

# Handle new user input
if user_input := st.chat_input("Ask a question..."):
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        streamed_text = ""
        streamed_blocks = []

        try:
            with st.spinner("Thinking..."):
                stream = client.beta.messages.stream(
                    model="claude-sonnet-4-20250514",
                    max_tokens=200000,
                    messages=[{"role": "user", "content": user_input}],
                    mcp_servers=[{
                        "type": "url",
                        "url": f"{MCP_URL}/mcp/",
                        "name": "meta-ads"
                    }],
                    extra_headers={"anthropic-beta": "mcp-client-2025-04-04"}
                )

                # Process streaming blocks
                for block in stream:
                    streamed_blocks.append(block)

                    if hasattr(block, "text"):
                        streamed_text += block.text
                        placeholder.markdown(streamed_text)

                    elif hasattr(block, "content"):
                        # We show tool results only after full tool result block is received
                        continue

                    elif getattr(block, "type", "") == "mcp_tool_use":
                        continue  # show after loop ends

        except Exception as e:
            placeholder.error(f"❌ Error: {e}")

        # After stream ends, render non-text blocks
        for block in streamed_blocks:
            if hasattr(block, "content"):
                with st.expander("🔧 Tool Result", expanded=False):
                    for sub_block in block.content:
                        if hasattr(sub_block, "text"):
                            st.markdown(sub_block.text)

            elif getattr(block, "type", "") == "mcp_tool_use":
                with st.expander(f"⚙️ Tool Called: `{block.name}`", expanded=False):
                    st.markdown("**Input:**")
                    st.json(block.input)

        # Save this turn to chat history
        st.session_state.chat_history.append({
            "user": user_input,
            "claude_blocks": streamed_blocks
        })
