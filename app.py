import streamlit as st
import anthropic
import os
import html

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
    st.session_state.chat_history = []

# JS clipboard button generator
def copy_button_js(text, key="copy"):
    escaped = html.escape(text).replace("`", "\\`")  # Escape backticks
    return f"""
    <button onclick="navigator.clipboard.writeText(`{escaped}`); alert('📋 Copied!')" 
    style='margin-top: 4px; padding:4px 8px; font-size:0.85rem;'>📋 Copy</button>
    """

# Display full chat history
for idx, entry in enumerate(st.session_state.chat_history):
    with st.chat_message("user"):
        st.markdown(entry["user"])
        st.markdown(copy_button_js(entry["user"], f"user_copy_{idx}"), unsafe_allow_html=True)

    with st.chat_message("assistant"):
        for jdx, block in enumerate(entry["claude_blocks"]):
            if hasattr(block, "text"):
                st.markdown(block.text)
                st.markdown(copy_button_js(block.text, f"asst_copy_{idx}_{jdx}"), unsafe_allow_html=True)

            elif hasattr(block, "content"):
                with st.expander("🔧 Tool Result", expanded=False):
                    for kdx, sub_block in enumerate(block.content):
                        if hasattr(sub_block, "text"):
                            st.markdown(sub_block.text)
                            st.markdown(copy_button_js(sub_block.text, f"tool_copy_{idx}_{jdx}_{kdx}"), unsafe_allow_html=True)

            elif getattr(block, "type", "") == "mcp_tool_use":
                with st.expander(f"⚙️ Tool Called: `{block.name}`", expanded=False):
                    st.markdown("**Input:**")
                    st.json(block.input)

# Handle new user input
if user_input := st.chat_input("Ask a question..."):
    with st.chat_message("user"):
        st.markdown(user_input)
        st.markdown(copy_button_js(user_input, "live_user_copy"), unsafe_allow_html=True)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = client.beta.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=10000,
                    messages=[{"role": "user", "content": user_input}],
                    mcp_servers=[{
                        "type": "url",
                        "url": f"{MCP_URL}/mcp/",
                        "name": "meta-ads"
                    }],
                    extra_headers={"anthropic-beta": "mcp-client-2025-04-04"}
                )

                blocks_to_store = []
                for block in response.content:
                    blocks_to_store.append(block)

                    if hasattr(block, "text"):
                        st.markdown(block.text)
                        st.markdown(copy_button_js(block.text, "live_asst_copy"), unsafe_allow_html=True)

                    elif hasattr(block, "content"):
                        with st.expander("🔧 Tool Result", expanded=False):
                            for sub_block in block.content:
                                if hasattr(sub_block, "text"):
                                    st.markdown(sub_block.text)
                                    st.markdown(copy_button_js(sub_block.text, "live_tool_copy"), unsafe_allow_html=True)

                    elif getattr(block, "type", "") == "mcp_tool_use":
                        with st.expander(f"⚙️ Tool Called: `{block.name}`", expanded=False):
                            st.markdown("**Input:**")
                            st.json(block.input)

                # Save chat turn
                st.session_state.chat_history.append({
                    "user": user_input,
                    "claude_blocks": blocks_to_store
                })

            except Exception as e:
                st.error(f"❌ Error: {e}")
