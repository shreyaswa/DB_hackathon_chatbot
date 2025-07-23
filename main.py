import streamlit as st
import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")

# --- Backend Prompt Placeholders ---
DEFAULT_SYSTEM_PROMPT = "You are FinBot, a helpful and friendly AI assistant for small business finance. Keep your responses concise and relevant to the provided information or the current conversation flow."
# Load the content of prompt.txt into FILE_ANALYSIS_TRIGGER_PROMPT
with open("prompt.txt", "r", encoding="utf-8") as file:
    FILE_ANALYSIS_TRIGGER_PROMPT = file.read()
# --- Conversational States ---
# Define different stages/flows of the conversation
FLOW_WELCOME = "welcome"
FLOW_NEW_BUSINESS_START = "new_business_start"
FLOW_NEW_BUSINESS_IDEA = "new_business_idea"
FLOW_NEW_BUSINESS_NO_IDEA = "new_business_no_idea"
FLOW_EXISTING_BUSINESS_NEEDS = "existing_business_needs"
FLOW_LEARN_MORE_TOPICS = "learn_more_topics"
FLOW_FREE_TEXT = "free_text"
FLOW_HUMAN_SUPPORT = "human_support"
FLOW_FILE_ANALYSIS = "file_analysis" # For when a file is being analyzed

# --- Modular Functions ---

def initialize_session_state():
    """Initializes Streamlit session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "uploaded_file_content" not in st.session_state:
        st.session_state.uploaded_file_content = None
    if "uploaded_file_name" not in st.session_state:
        st.session_state.uploaded_file_name = None
    if "file_analysis_triggered" not in st.session_state:
        st.session_state.file_analysis_triggered = False
    # New: Track the current conversational flow
    if "current_flow" not in st.session_state:
        st.session_state.current_flow = FLOW_WELCOME
    # New: Track the last button clicked to manage flow transitions
    if "last_button_click" not in st.session_state:
        st.session_state.last_button_click = None

def display_chat_history():
    """Displays existing chat messages from session state."""
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

def display_options_buttons(options: dict):
    """
    Displays a row of clickable buttons for conversational options.
    Args:
        options (dict): A dictionary where keys are button labels and values are the flow to transition to.
    """
    cols = st.columns(len(options))
    for i, (label, flow) in enumerate(options.items()):
        with cols[i]:
            # Generate a unique key by combining the flow and the current_flow context
            button_key = f"btn_{flow}_{st.session_state.current_flow}_{i}"
            if st.button(label, key=button_key):
                st.session_state.last_button_click = label # Store which button was clicked
                st.session_state.current_flow = flow
                st.rerun() # Rerun to process the button click and transition flow

def get_ollama_response(user_prompt: str, chat_history: list, system_prompt: str = DEFAULT_SYSTEM_PROMPT, file_content: str = None) -> str:
    """
    Sends the chat history and optional file content to Ollama and streams the response.
    """
    full_response = ""
    message_placeholder = st.empty()

    try:
        ollama_messages = [
            {"role": "system", "content": system_prompt}
        ]

        if file_content:
            ollama_messages.append({"role": "user", "content": f"The following is content from a file named '{st.session_state.uploaded_file_name}':\n\n```\n{file_content}\n```\n\nPlease analyze this content in the context of our conversation."})

        # Add existing chat history to maintain context
        # Filter out internal messages like "Processing file..."
        filtered_chat_history = [
            msg for msg in chat_history
            if not msg["content"].startswith("File '") and not msg["content"].startswith("Thinking about the file content...")
        ]
        ollama_messages.extend([{"role": m["role"], "content": m["content"]} for m in filtered_chat_history])

        ollama_messages.append({"role": "user", "content": user_prompt})

        payload = {
            "model": OLLAMA_MODEL,
            "messages": ollama_messages,
            "stream": True
        }

        with requests.post(f"{OLLAMA_API_BASE}/api/chat", json=payload, stream=True) as response:
            response.raise_for_status()

            for line in response.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line.decode('utf-8'))
                        if "message" in chunk and "content" in chunk["message"]:
                            content_chunk = chunk["message"]["content"]
                            full_response += content_chunk
                            message_placeholder.markdown(full_response + "▌")
                    except json.JSONDecodeError:
                        continue
            message_placeholder.markdown(full_response)

    except requests.exceptions.ConnectionError:
        st.error(f"Could not connect to Ollama server at {OLLAMA_API_BASE}. Please ensure Ollama is running and the model '{OLLAMA_MODEL}' is pulled.")
        full_response = "I'm sorry, I can't connect to the local LLM. Please check if Ollama is running."
        message_placeholder.markdown(full_response)
    except requests.exceptions.HTTPError as e:
        st.error(f"Ollama API Error: {e.response.status_code} - {e.response.text}")
        full_response = "I'm sorry, I encountered an error with the Ollama API. Please check the server logs."
        message_placeholder.markdown(full_response)
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        full_response = "An unexpected error occurred. Please check your Ollama setup."
        message_placeholder.markdown(full_response)

    return full_response

# --- Main Application Logic ---
def main():
    """Main function to run the Streamlit chatbot application."""
    if not OLLAMA_API_BASE:
        st.error("OLLAMA_API_BASE environment variable is not set. Please create a .env file or set the variable.")
        st.stop()
    if not OLLAMA_MODEL:
        st.error("OLLAMA_MODEL environment variable is not set. Please create a .env file or set the variable.")
        st.stop()

    st.set_page_config(page_title=f"FinBot ({OLLAMA_MODEL.capitalize()})", layout="centered")
    st.title(f"🤖 FinBot (via Ollama)")
    st.markdown("---")

    initialize_session_state()

    # --- Conversational Flow Logic ---
    # Display welcome message and options if it's a new session or returning to welcome
    if st.session_state.current_flow == FLOW_WELCOME:
        if not st.session_state.messages or st.session_state.messages[-1]["content"] != "Hi 👋 I’m FinBot, your small business finance buddy. I can help you track cash flow, check funding options, or give you smart budget tips. Let’s get started — what do you want help with today?":
            st.session_state.messages.append({"role": "assistant", "content": "Hi 👋 I’m FinBot, your small business finance buddy. I can help you track cash flow, check funding options, or give you smart budget tips. Let’s get started — what do you want help with today?"})
        display_chat_history()
        options = {
            "I’m just starting my business": FLOW_NEW_BUSINESS_START,
            "I already run a business": FLOW_EXISTING_BUSINESS_NEEDS,
            "I want funding help": FLOW_FREE_TEXT, # Can be a specific flow later
            "I want to track my cash flow": FLOW_FREE_TEXT, # Can be a specific flow later
            "I want to learn more": FLOW_LEARN_MORE_TOPICS,
            "I have a question": FLOW_FREE_TEXT
        }
        display_options_buttons(options)

    elif st.session_state.current_flow == FLOW_NEW_BUSINESS_START:
        if st.session_state.last_button_click == "I’m just starting my business" and (not st.session_state.messages or st.session_state.messages[-1]["content"] != "Great! Let’s build a strong base together. Do you have a business idea yet?"):
            st.session_state.messages.append({"role": "user", "content": st.session_state.last_button_click}) # Show user's click
            st.session_state.messages.append({"role": "assistant", "content": "Great! Let’s build a strong base together. Do you have a business idea yet?"})
            st.session_state.last_button_click = None # Reset
        display_chat_history()
        options = {
            "Yes, I have an idea": FLOW_NEW_BUSINESS_IDEA,
            "No, I need help choosing": FLOW_NEW_BUSINESS_NO_IDEA
        }
        display_options_buttons(options)

    elif st.session_state.current_flow == FLOW_NEW_BUSINESS_IDEA:
        if st.session_state.last_button_click == "Yes, I have an idea" and (not st.session_state.messages or st.session_state.messages[-1]["content"] != "Awesome! Do you know roughly how much money you’ll need to start?"):
            st.session_state.messages.append({"role": "user", "content": st.session_state.last_button_click}) # Show user's click
            st.session_state.messages.append({"role": "assistant", "content": "Awesome! Do you know roughly how much money you’ll need to start?"})
            st.session_state.messages.append({"role": "assistant", "content": "*(Placeholder: Offer simple planning template)*"})
            st.session_state.last_button_click = None # Reset
        display_chat_history()
        # No new buttons, user can type or go back to welcome
        st.markdown("---")
        if st.button("Back to Main Menu", key="back_to_welcome_idea"):
            st.session_state.current_flow = FLOW_WELCOME
            st.rerun()

    elif st.session_state.current_flow == FLOW_NEW_BUSINESS_NO_IDEA:
        if st.session_state.last_button_click == "No, I need help choosing" and (not st.session_state.messages or st.session_state.messages[-1]["content"] != "No worries! I can show you some small business ideas that need low investment. Want to see them?"):
            st.session_state.messages.append({"role": "user", "content": st.session_state.last_button_click}) # Show user's click
            st.session_state.messages.append({"role": "assistant", "content": "No worries! I can show you some small business ideas that need low investment. Want to see them?"})
            st.session_state.messages.append({"role": "assistant", "content": "*(Placeholder: Link to blog/articles for ideas)*"})
            st.session_state.last_button_click = None # Reset
        display_chat_history()
        st.markdown("---")
        if st.button("Back to Main Menu", key="back_to_welcome_no_idea"):
            st.session_state.current_flow = FLOW_WELCOME
            st.rerun()

    elif st.session_state.current_flow == FLOW_EXISTING_BUSINESS_NEEDS:
        if st.session_state.last_button_click == "I already run a business" and (not st.session_state.messages or st.session_state.messages[-1]["content"] != "Good to know! What’s your biggest need right now?"):
            st.session_state.messages.append({"role": "user", "content": st.session_state.last_button_click}) # Show user's click
            st.session_state.messages.append({"role": "assistant", "content": "Good to know! What’s your biggest need right now?"})
            st.session_state.last_button_click = None # Reset
        display_chat_history()
        options = {
            "Track cash flow": FLOW_FREE_TEXT, # Placeholder for specific flow
            "Check funding eligibility": FLOW_FREE_TEXT, # Placeholder for specific flow
            "Get budget advice": FLOW_FREE_TEXT, # Placeholder for specific flow
            "Improve financial health score": FLOW_FREE_TEXT, # Placeholder for specific flow
            "Other": FLOW_FREE_TEXT
        }
        display_options_buttons(options)

    elif st.session_state.current_flow == FLOW_LEARN_MORE_TOPICS:
        if st.session_state.last_button_click == "I want to learn more" and (not st.session_state.messages or st.session_state.messages[-1]["content"] != "Perfect! I can share guides, checklists, or tips for you. What do you want to learn about?"):
            st.session_state.messages.append({"role": "user", "content": st.session_state.last_button_click}) # Show user's click
            st.session_state.messages.append({"role": "assistant", "content": "Perfect! I can share guides, checklists, or tips for you. What do you want to learn about?"})
            st.session_state.last_button_click = None # Reset
        display_chat_history()
        options = {
            "How to budget better": FLOW_FREE_TEXT,
            "How to save money": FLOW_FREE_TEXT,
            "How to get more customers": FLOW_FREE_TEXT,
            "How to file taxes": FLOW_FREE_TEXT,
            "Other": FLOW_FREE_TEXT
        }
        display_options_buttons(options)

    # This flow handles all free-text input and also acts as a general chat mode
    # It's also the target for some initial button clicks that don't have a dedicated sub-flow yet.
    elif st.session_state.current_flow == FLOW_FREE_TEXT or st.session_state.current_flow == FLOW_FILE_ANALYSIS:
        # If we just transitioned from a button click to FREE_TEXT, add that click to history
        if st.session_state.last_button_click:
            st.session_state.messages.append({"role": "user", "content": st.session_state.last_button_click})
            st.session_state.last_button_click = None # Reset after adding to history
            st.session_state.current_flow = FLOW_FREE_TEXT # Ensure we are in free text mode

        display_chat_history()
        st.markdown("---")
        # Add a button to return to the main menu from free text mode
        if st.button("Back to Main Menu", key="back_to_welcome_free_text"):
            st.session_state.current_flow = FLOW_WELCOME
            st.rerun()

    # --- File Uploader Section (moved to be closer to chat input) ---
    # Moved from below the chat input to above it for better integration.
    # Removed subheader to make it feel less like a separate section.
    uploaded_file = st.file_uploader(
        "Upload a document for analysis (e.g., .txt, .md)",
        type=["txt", "md"],
        key="file_uploader_main" # Unique key for this widget
    )

    current_file_content = None
    if uploaded_file is not None:
        # If a new file is uploaded or a different file, process it
        if st.session_state.uploaded_file_name != uploaded_file.name:
            st.session_state.uploaded_file_name = uploaded_file.name
            st.session_state.uploaded_file_content = uploaded_file.read().decode("utf-8")
            st.session_state.file_analysis_triggered = False # Reset trigger for new file
            st.session_state.messages.append({"role": "assistant", "content": f"File '{uploaded_file.name}' uploaded successfully. Analyzing content..."})
            st.session_state.current_flow = FLOW_FILE_ANALYSIS # Set flow to file analysis
            st.rerun() # Rerun to display confirmation and trigger analysis
        current_file_content = st.session_state.uploaded_file_content

        # Trigger initial analysis if a new file is uploaded and not yet analyzed
        if current_file_content and not st.session_state.file_analysis_triggered:
            with st.chat_message("assistant"):
                thinking_placeholder = st.empty()
                thinking_placeholder.markdown("Thinking about the file content...")

                initial_analysis_response = get_ollama_response(
                    user_prompt=FILE_ANALYSIS_TRIGGER_PROMPT,
                    chat_history=[], # Start fresh for this initial analysis context
                    file_content=current_file_content
                )
                thinking_placeholder.empty()
                st.session_state.messages.append({"role": "assistant", "content": initial_analysis_response})
                st.session_state.file_analysis_triggered = True
                st.session_state.current_flow = FLOW_FREE_TEXT # After analysis, switch to free text mode
                st.rerun() # Rerun to display the initial analysis

    # --- Main Chat Input (always available for free text) ---
    # This input is separate from the flow buttons and allows user to type at any time.
    if prompt := st.chat_input("Type your message here, or upload a file above...", key="main_chat_input"):
        # If user types, switch to free text mode if not already there
        if st.session_state.current_flow not in [FLOW_FREE_TEXT, FLOW_FILE_ANALYSIS]:
            st.session_state.current_flow = FLOW_FREE_TEXT

        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Handle "Live Agent" command
        if prompt.lower() == "live agent":
            st.session_state.messages.append({"role": "assistant", "content": "Connecting you to a human expert. Please wait a moment."})
            st.session_state.current_flow = FLOW_HUMAN_SUPPORT
            st.rerun() # Rerun to display message
        else:
            # For general free text, use the current chat history (which includes file content if processed)
            assistant_response = get_ollama_response(prompt, st.session_state.messages, file_content=st.session_state.uploaded_file_content if st.session_state.file_analysis_triggered else None)
            st.session_state.messages.append({"role": "assistant", "content": assistant_response})

    # --- Human Support Message ---
    if st.session_state.current_flow == FLOW_HUMAN_SUPPORT:
        st.markdown("---")
        st.info("Want to talk to our human expert? Type 'Live Agent' or click below.")
        if st.button("Talk to a Human Expert", key="human_expert_button"):
            st.session_state.messages.append({"role": "assistant", "content": "Our human expert will be with you shortly. Please provide your contact details."})
            # Placeholder for actual human support integration
            st.markdown("*(Placeholder: Integration with live chat system or contact form)*")
            st.session_state.current_flow = FLOW_FREE_TEXT # Return to free text after displaying message

    # st.markdown("---")
    # st.info(f"This chatbot uses the '{OLLAMA_MODEL}' model via Ollama. Ensure Ollama is running and the model is downloaded.")

if __name__ == "__main__":
    main()
