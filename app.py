import streamlit as st
import pandas as pd
import os
import time
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def upload_files_to_openai():
    """Upload CSV files to OpenAI and create assistant with code interpreter"""
    try:
        # Get API key from environment or Streamlit secrets
        api_key = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY")
        if not api_key:
            st.error("OpenAI API key not found. Please add it to your .env file or Streamlit secrets.")
            return None, []
        
        client = OpenAI(api_key=api_key)
        
        file_ids = []
        csv_files = ["accounts.csv", "invoices.csv", "bills.csv", "expenses.csv"]
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Upload files
        for i, filename in enumerate(csv_files):
            filepath = os.path.join("anonymized_data", filename)
            if os.path.exists(filepath):
                status_text.text(f"Uploading {filename}...")
                
                with open(filepath, "rb") as file:
                    uploaded_file = client.files.create(
                        file=file,
                        purpose="assistants"
                    )
                    file_ids.append(uploaded_file.id)
                
                progress_bar.progress((i + 1) / len(csv_files))
        
        # Create assistant with code interpreter
        status_text.text("Creating AI assistant with code interpreter...")
        assistant = client.beta.assistants.create(
            name="Fashion Textile Data Analyst",
            instructions="""You are a data analyst for a fashion textile business. You have access to CSV files containing:
            - accounts.csv: Chart of accounts with balances and account types
            - invoices.csv: Customer invoices with amounts and dates
            - bills.csv: Vendor bills and payments
            - expenses.csv: Business expenses and categorization
            
            When asked questions, analyze the data using Python code and provide insights. Always write and execute code to answer questions accurately with real calculations.""",
            tools=[{"type": "code_interpreter"}],
            tool_resources={
                "code_interpreter": {
                    "file_ids": file_ids
                }
            },
            model="gpt-4o"
        )
        
        status_text.text("Assistant created successfully!")
        return assistant.id, file_ids
        
    except Exception as e:
        st.error(f"Error uploading files: {str(e)}")
        return None, []

def analysis_stream(text, placeholder):
    """Analysis function using OpenAI Assistants API with code interpreter"""
    try:
        # Check if assistant is created
        if "openai_assistant_id" not in st.session_state or not st.session_state.openai_assistant_id:
            placeholder.error("Please start a session first to create the assistant.")
            return
        
        # Get API key
        api_key = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY")
        if not api_key:
            placeholder.error("OpenAI API key not found.")
            return
        
        client = OpenAI(api_key=api_key)
        
        placeholder.info("Analyzing your data with code interpreter...")
        
        # Create a thread for the conversation
        thread = client.beta.threads.create()
        
        # Add user message to thread
        message = client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=text
        )
        
        # Create and stream the run
        response_text = ""
        with client.beta.threads.runs.stream(
            thread_id=thread.id,
            assistant_id=st.session_state.openai_assistant_id,
        ) as stream:
            for event in stream:
                # Only handle text streaming, skip code display
                if event.event == 'thread.message.delta':
                    delta = event.data.delta
                    if delta.content:
                        for content in delta.content:
                            if content.type == 'text' and content.text:
                                if content.text.value:
                                    response_text += content.text.value
                                    # Show streaming text with cursor
                                    placeholder.markdown(response_text + "▌")
        
        # Final response without cursor
        if response_text:
            placeholder.markdown(response_text)
        else:
            placeholder.success("Analysis completed!")
        
    except Exception as e:
        placeholder.error(f"Error analyzing text: {str(e)}")
        st.error(f"Full error details: {e}")

def analysis(text):
    """Non-streaming analysis function for backward compatibility"""
    try:
        # Check if files are uploaded
        if "openai_file_ids" not in st.session_state or not st.session_state.openai_file_ids:
            return "Please start a session first to upload files to OpenAI."
        
        # Get API key
        api_key = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY")
        if not api_key:
            return "OpenAI API key not found."
        
        client = OpenAI(api_key=api_key)
        
        # Create a response using the uploaded files
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are an AI assistant analyzing accounting data for a fashion textile business. The user has uploaded CSV files containing accounts, customers, invoices, services, vendors, bills, and expenses data. Provide helpful insights and analysis based on their questions."
                },
                {
                    "role": "user",
                    "content": text
                }
            ],
            temperature=0.7,
            max_tokens=1000
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        return f"Error analyzing text: {str(e)}"

def start_session():
    """Start Session function - Upload files to OpenAI and create assistant"""
    try:
        st.session_state.session_active = True
        
        # Upload files to OpenAI and create assistant
        with st.spinner("Uploading files and creating AI assistant..."):
            assistant_id, file_ids = upload_files_to_openai()
            
        if assistant_id and file_ids:
            st.session_state.openai_assistant_id = assistant_id
            st.session_state.openai_file_ids = file_ids
            return f"Session started successfully! Created AI assistant with {len(file_ids)} files for code interpreter analysis."
        else:
            return "Session started but failed to create assistant or upload files."
            
    except Exception as e:
        return f"Error starting session: {str(e)}"

@st.cache_data
def load_csv_data(filename):
    """Load CSV data with caching"""
    filepath = os.path.join("anonymized_data", filename)
    if os.path.exists(filepath):
        return pd.read_csv(filepath)
    else:
        st.error(f"File {filename} not found in anonymized_data folder")
        return pd.DataFrame()

def search_dataframe(df, search_term, search_columns=None):
    """Search dataframe across specified columns or all columns"""
    if df.empty or not search_term:
        return df
    
    if search_columns is None:
        search_columns = df.columns
    
    # Create boolean mask for search
    mask = pd.Series([False] * len(df))
    for col in search_columns:
        if col in df.columns:
            mask |= df[col].astype(str).str.contains(search_term, case=False, na=False)
    
    return df[mask]

# Set page config
st.set_page_config(
    page_title="Fashion Textile - Accounting",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Sidebar navigation
st.sidebar.title("Fashion Textile Accounting")
st.sidebar.markdown("---")

# Main navigation
page = st.sidebar.radio(
    "Navigate to:",
    [
        "Home",
        "Accounts", 
        "Services",
        "Customers",
        "Invoices",
        "Vendors",
        "Bills", 
        "Expenses"
    ]
)

# Home Page
if page == "Home":
    st.title("Fashion Textile Accounting System")
    st.markdown("---")
    st.write("Welcome to your comprehensive accounting system for fashion and textile business.")
    
    # Session Management
    st.subheader("Session Management")
    
    # Initialize session state
    if "session_active" not in st.session_state:
        st.session_state.session_active = False
    
    # Start Session button
    if not st.session_state.session_active:
        if st.button("Start Session", type="primary"):
            result = start_session()
            st.success(result)
            st.rerun()
    else:
        st.success("✅ Session is active")
        if st.button("End Session", type="secondary"):
            st.session_state.session_active = False
            st.info("Session ended")
            st.rerun()
    
    st.markdown("---")
    
    # Analysis Tool
    st.subheader("Analysis Tool")
    
    # Check if session is active before allowing analysis
    if st.session_state.session_active:
        # Text input
        user_input = st.text_area("Enter text for analysis:", placeholder="Type your text here...")
        
        # Analyze button
        if st.button("Analyze"):
            if user_input:
                st.write("**Result:**")
                
                # Create placeholder for streaming response
                response_placeholder = st.empty()
                response_placeholder.info("🤔 Thinking...")
                
                # Stream the analysis response
                analysis_stream(user_input, response_placeholder)
            else:
                st.warning("Please enter some text to analyze.")
    else:
        st.warning("Please start a session to use the analysis tool.")
        st.text_area("Enter text for analysis:", placeholder="Type your text here...", disabled=True)
        st.button("Analyze", disabled=True)
    
    st.markdown("---")
    
    # Overview sections
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("Accounts Module")
        st.write("- Chart of Accounts management")
        
    with col2:
        st.subheader("Sales Module") 
        st.write("- Services management")
        st.write("- Customer database")
        st.write("- Invoice creation")
    
    with col3:
        st.subheader("Expenses Module")
        st.write("- Vendor management")
        st.write("- Bill tracking")
        st.write("- Expense recording")

# Accounts Page
elif page == "Accounts":
    st.title("Accounts")
    st.markdown("---")
    
    # Load accounts data
    accounts_df = load_csv_data("accounts.csv")
    
    if not accounts_df.empty:
        st.subheader(f"Chart of Accounts ({len(accounts_df)} accounts)")
        
        # Search functionality
        search_term = st.text_input("Search accounts:", placeholder="Search by name, type, or description...")
        
        # Filter data based on search
        if search_term:
            filtered_df = search_dataframe(accounts_df, search_term)
            st.write(f"Found {len(filtered_df)} matching accounts")
        else:
            filtered_df = accounts_df
        
        # Display data
        st.dataframe(filtered_df, use_container_width=True)
        
        # Summary statistics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Accounts", len(accounts_df))
        with col2:
            active_accounts = accounts_df[accounts_df['Active'] == True].shape[0] if 'Active' in accounts_df.columns else 0
            st.metric("Active Accounts", active_accounts)
        with col3:
            total_balance = accounts_df['current_balance'].sum() if 'current_balance' in accounts_df.columns else 0
            st.metric("Total Balance", f"${total_balance:,.2f}")
    else:
        st.error("No accounts data available")

# Services Page
elif page == "Services":
    st.title("Services")
    st.markdown("---")
    
    # Load services data
    services_df = load_csv_data("services.csv")
    
    if not services_df.empty:
        st.subheader(f"Services Catalog ({len(services_df)} services)")
        
        # Search functionality
        search_term = st.text_input("Search services:", placeholder="Search by name, description, or type...")
        
        # Filter data based on search
        if search_term:
            filtered_df = search_dataframe(services_df, search_term)
            st.write(f"Found {len(filtered_df)} matching services")
        else:
            filtered_df = services_df
        
        # Display data
        st.dataframe(filtered_df, use_container_width=True)
        
        # Summary statistics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Services", len(services_df))
        with col2:
            active_services = services_df[services_df['Active'] == True].shape[0] if 'Active' in services_df.columns else 0
            st.metric("Active Services", active_services)
        with col3:
            avg_price = services_df['UnitPrice'].mean() if 'UnitPrice' in services_df.columns else 0
            st.metric("Avg Unit Price", f"${avg_price:.2f}")
    else:
        st.error("No services data available")

# Customers Page
elif page == "Customers":
    st.title("Customers")
    st.markdown("---")
    
    # Load customers data
    customers_df = load_csv_data("customers.csv")
    
    if not customers_df.empty:
        st.subheader(f"Customer Database ({len(customers_df)} customers)")
        
        # Search functionality
        search_term = st.text_input("Search customers:", placeholder="Search by name, company, email, or city...")
        
        # Filter data based on search
        if search_term:
            filtered_df = search_dataframe(customers_df, search_term)
            st.write(f"Found {len(filtered_df)} matching customers")
        else:
            filtered_df = customers_df
        
        # Display data
        st.dataframe(filtered_df, use_container_width=True)
        
        # Summary statistics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Customers", len(customers_df))
        with col2:
            active_customers = customers_df[customers_df['Active'] == True].shape[0] if 'Active' in customers_df.columns else 0
            st.metric("Active Customers", active_customers)
        with col3:
            total_balance = customers_df['Balance'].sum() if 'Balance' in customers_df.columns else 0
            st.metric("Total A/R Balance", f"${total_balance:,.2f}")
    else:
        st.error("No customers data available")

# Invoices Page
elif page == "Invoices":
    st.title("Invoices")
    st.markdown("---")
    
    # Load invoices data
    invoices_df = load_csv_data("invoices.csv")
    
    if not invoices_df.empty:
        st.subheader(f"Invoice Management ({len(invoices_df)} invoices)")
        
        # Search functionality
        search_term = st.text_input("Search invoices:", placeholder="Search by invoice number, customer, or amount...")
        
        # Filter data based on search
        if search_term:
            filtered_df = search_dataframe(invoices_df, search_term)
            st.write(f"Found {len(filtered_df)} matching invoices")
        else:
            filtered_df = invoices_df
        
        # Display data
        st.dataframe(filtered_df, use_container_width=True)
        
        # Summary statistics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Invoices", len(invoices_df))
        with col2:
            if 'TotalAmt' in invoices_df.columns:
                total_amount = invoices_df['TotalAmt'].sum()
                st.metric("Total Invoice Amount", f"${total_amount:,.2f}")
            else:
                st.metric("Total Invoice Amount", "N/A")
        with col3:
            if 'Balance' in invoices_df.columns:
                outstanding_balance = invoices_df['Balance'].sum()
                st.metric("Outstanding Balance", f"${outstanding_balance:,.2f}")
            else:
                st.metric("Outstanding Balance", "N/A")
    else:
        st.error("No invoices data available")

# Vendors Page
elif page == "Vendors":
    st.title("Vendors")
    st.markdown("---")
    
    # Load vendors data
    vendors_df = load_csv_data("vendors.csv")
    
    if not vendors_df.empty:
        st.subheader(f"Vendor Management ({len(vendors_df)} vendors)")
        
        # Search functionality
        search_term = st.text_input("Search vendors:", placeholder="Search by name, company, email, or city...")
        
        # Filter data based on search
        if search_term:
            filtered_df = search_dataframe(vendors_df, search_term)
            st.write(f"Found {len(filtered_df)} matching vendors")
        else:
            filtered_df = vendors_df
        
        # Display data
        st.dataframe(filtered_df, use_container_width=True)
        
        # Summary statistics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Vendors", len(vendors_df))
        with col2:
            active_vendors = vendors_df[vendors_df['Active'] == True].shape[0] if 'Active' in vendors_df.columns else 0
            st.metric("Active Vendors", active_vendors)
        with col3:
            total_balance = vendors_df['Balance'].sum() if 'Balance' in vendors_df.columns else 0
            st.metric("Total A/P Balance", f"${total_balance:,.2f}")
    else:
        st.error("No vendors data available")

# Bills Page
elif page == "Bills":
    st.title("Bills")
    st.markdown("---")
    
    # Load bills data
    bills_df = load_csv_data("bills.csv")
    
    if not bills_df.empty:
        st.subheader(f"Bills Management ({len(bills_df)} bills)")
        
        # Search functionality
        search_term = st.text_input("Search bills:", placeholder="Search by vendor, amount, or reference...")
        
        # Filter data based on search
        if search_term:
            filtered_df = search_dataframe(bills_df, search_term)
            st.write(f"Found {len(filtered_df)} matching bills")
        else:
            filtered_df = bills_df
        
        # Display data
        st.dataframe(filtered_df, use_container_width=True)
        
        # Summary statistics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Bills", len(bills_df))
        with col2:
            if 'TotalAmt' in bills_df.columns:
                total_amount = bills_df['TotalAmt'].sum()
                st.metric("Total Bill Amount", f"${total_amount:,.2f}")
            else:
                st.metric("Total Bill Amount", "N/A")
        with col3:
            if 'Balance' in bills_df.columns:
                outstanding_balance = bills_df['Balance'].sum()
                st.metric("Outstanding Balance", f"${outstanding_balance:,.2f}")
            else:
                st.metric("Outstanding Balance", "N/A")
    else:
        st.error("No bills data available")

# Expenses Page
elif page == "Expenses":
    st.title("Expenses")
    st.markdown("---")
    
    # Load expenses data
    expenses_df = load_csv_data("expenses.csv")
    
    if not expenses_df.empty:
        st.subheader(f"Expense Management ({len(expenses_df)} expenses)")
        
        # Search functionality
        search_term = st.text_input("Search expenses:", placeholder="Search by amount, payment type, or memo...")
        
        # Filter data based on search
        if search_term:
            filtered_df = search_dataframe(expenses_df, search_term)
            st.write(f"Found {len(filtered_df)} matching expenses")
        else:
            filtered_df = expenses_df
        
        # Display data
        st.dataframe(filtered_df, use_container_width=True)
        
        # Summary statistics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Expenses", len(expenses_df))
        with col2:
            if 'TotalAmt' in expenses_df.columns:
                total_amount = expenses_df['TotalAmt'].sum()
                st.metric("Total Expense Amount", f"${total_amount:,.2f}")
            else:
                st.metric("Total Expense Amount", "N/A")
        with col3:
            if 'PaymentType' in expenses_df.columns:
                payment_types = expenses_df['PaymentType'].nunique()
                st.metric("Payment Methods", payment_types)
            else:
                st.metric("Payment Methods", "N/A")
    else:
        st.error("No expenses data available")

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("Fashion Textile Accounting v1.0")
st.sidebar.markdown("Built with Streamlit") 