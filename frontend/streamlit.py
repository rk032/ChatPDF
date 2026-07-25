# frontend/app.py
import streamlit as st
import requests
import json
from typing import Optional
import time

# API Configuration
API_BASE_URL = "http://localhost:8000"  # Update with your API URL

class APIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = requests.Session()

    def register(self, email: str, password: str) -> dict:
        response = requests.post(
            f"{self.base_url}/register",
            json={"email": email, "password": password}
        )
        return response.json() if response.ok else None

    def login(self, email: str, password: str) -> Optional[str]:
        response = requests.post(
            f"{self.base_url}/token",
            json={"username": email, "password": password}  # Use json instead of data
        )
        if response.ok:
            return response.json()
        return None


    def upload_pdfs(self, files):
        files_dict = {f"files": (file.name, file, "application/pdf") for file in files}
        
        response = requests.post(
            f"{self.base_url}/upload-pdfs",  # No need for token anymore
            files=files_dict
        )
        return response.json() if response.ok else None

    def ask_question(self, question: str) -> Optional[str]:
        response = requests.post(
            f"{self.base_url}/ask",  # No need for token anymore
            json={"question": question}
        )
        return response.json()["answer"] if response.ok else None

# Initialize API client
api_client = APIClient(API_BASE_URL)

def render_login_page():
    st.title("Welcome Back 👋")
    
    with st.container():
        st.markdown("""<style> ... </style>""", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            if "login_email" not in st.session_state:
                st.session_state.login_email = ""
            if "login_password" not in st.session_state:
                st.session_state.login_password = ""
                
            def handle_login():
                if st.session_state.login_email and st.session_state.login_password:
                    with st.spinner("Logging in..."):
                        response = api_client.login(
                            st.session_state.login_email,
                            st.session_state.login_password
                        )
                        if response and response.get("message") == "Login successful":
                            st.session_state.user_email = st.session_state.login_email
                            st.session_state.page = "chat"
                            st.rerun()
                        else:
                            st.error("Invalid email or password!")
                else:
                    st.warning("Please fill in all fields")
            
            with st.form("login_form", clear_on_submit=False):
                st.subheader("Login to Your Account")
                st.text_input("Email Address", key="login_email", placeholder="your@email.com")
                st.text_input("Password", key="login_password", type="password", placeholder="Enter your password")
                st.form_submit_button("Sign In", use_container_width=True, on_click=handle_login)
            
            st.markdown("<div style='text-align: center;'>Don't have an account?</div>", unsafe_allow_html=True)
            if st.button("Create Account", use_container_width=True):
                st.session_state.page = "register"
                st.rerun()

def render_register_page():
    st.title("Create Account ✨")
    
    with st.container():
        st.markdown("""<style> ... </style>""", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            if "register_email" not in st.session_state:
                st.session_state.register_email = ""
            if "register_password" not in st.session_state:
                st.session_state.register_password = ""
            if "register_confirm" not in st.session_state:
                st.session_state.register_confirm = ""
                
            def handle_register():
                if not all([st.session_state.register_email, 
                          st.session_state.register_password, 
                          st.session_state.register_confirm]):
                    st.warning("Please fill in all fields")
                    return
                if st.session_state.register_password != st.session_state.register_confirm:
                    st.error("Passwords don't match!")
                    return
                if len(st.session_state.register_password) < 6:
                    st.error("Password must be at least 6 characters long!")
                    return
                
                with st.spinner("Creating account..."):
                    result = api_client.register(
                        st.session_state.register_email,
                        st.session_state.register_password
                    )
                    if result:
                        st.success("Registration successful! Please login.")
                        time.sleep(1)
                        st.session_state.page = "login"
                        st.rerun()
                    else:
                        st.error("Email already registered!")
            
            with st.form("register_form", clear_on_submit=False):
                st.subheader("Sign Up for Free")
                st.text_input("Email Address", key="register_email", placeholder="your@email.com")
                st.text_input("Password", key="register_password", type="password", placeholder="Choose a strong password")
                st.text_input("Confirm Password", key="register_confirm", type="password", placeholder="Repeat your password")
                st.markdown("<div>Password must be at least 6 characters long</div>", unsafe_allow_html=True)
                st.form_submit_button("Create Account", use_container_width=True, on_click=handle_register)
            
            st.markdown("<div style='text-align: center;'>Already have an account?</div>", unsafe_allow_html=True)
            if st.button("Back to Login", use_container_width=True):
                st.session_state.page = "login"
                st.rerun()

def render_chat_page():
    st.title("📄 PDF Chat Assistant")
    with st.sidebar:
        st.markdown(f"<h3>{st.session_state.user_email}</h3>", unsafe_allow_html=True)
        st.markdown("---")
        with st.expander("📁 Document Management", expanded=True):
            pdf_docs = st.file_uploader("Upload PDFs", accept_multiple_files=True, type=['pdf'])
            if st.button("Process Documents", use_container_width=True):
                if pdf_docs:
                    with st.spinner("Processing..."):
                        result = api_client.upload_pdfs(pdf_docs)
                        if result:
                            st.success("✅ Processing complete!")
                        else:
                            st.error("Error processing documents")
                else:
                    st.warning("Please upload PDFs first")
        if st.button("Logout", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.container():
            if message["role"] == "user":
                st.markdown(f"<div>{message['content']}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div>{message['content']}</div>", unsafe_allow_html=True)

    def handle_input():
        if st.session_state.user_input.strip():
            user_question = st.session_state.user_input
            st.session_state.messages.append({"role": "user", "content": user_question})
            with st.spinner("Thinking..."):
                response = api_client.ask_question(user_question)
                if response:
                    st.session_state.messages.append({"role": "assistant", "content": response})
                else:
                    st.error("Error getting response")
            st.session_state.user_input = ""

    with st.container():
        st.text_input("Ask a question...", key="user_input", on_change=handle_input)
        st.button("Send", use_container_width=True, on_click=handle_input)

def main():
    if 'page' not in st.session_state:
        st.session_state.page = 'login'
    
    if st.session_state.page == "login":
        render_login_page()
    elif st.session_state.page == "register":
        render_register_page()
    elif st.session_state.page == "chat":
        render_chat_page()

if __name__ == "__main__":
    main()
