"""
AI Resource Finder - Streamlit Application
"""

import sys
import os

# Add project root to Python path for imports
# Handle both local and Streamlit Cloud environments
try:
    _file_path = os.path.abspath(__file__)
    project_root = os.path.dirname(_file_path)
except NameError:
    # Fallback if __file__ is not available
    project_root = os.getcwd()

# Add project root to path - verify it has the expected structure
if project_root and os.path.exists(project_root):
    has_utils = os.path.exists(os.path.join(project_root, 'utils'))
    has_services = os.path.exists(os.path.join(project_root, 'services'))
    has_models = os.path.exists(os.path.join(project_root, 'models'))
    has_agents = os.path.exists(os.path.join(project_root, 'agents'))
    
    # If it has the expected structure, add it
    if (has_utils or has_services or has_models or has_agents) and project_root not in sys.path:
        sys.path.insert(0, project_root)

# Also add current working directory if different and it has the structure
cwd = os.getcwd()
if cwd != project_root and cwd and os.path.exists(cwd):
    has_utils = os.path.exists(os.path.join(cwd, 'utils'))
    has_services = os.path.exists(os.path.join(cwd, 'services'))
    if (has_utils or has_services) and cwd not in sys.path:
        sys.path.insert(0, cwd)

import streamlit as st
import json
from datetime import datetime
from typing import Dict, Any, Optional, List

from config import Config
from utils.database import DatabaseManager
from utils.bedrock_client import BedrockClient
from agents.orchestrator import orchestrator
from services.email_service import EmailService
from models.allocation import AllocationRequest

# Page configuration
st.set_page_config(
    page_title="AI Demand Hub",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for blue theme
st.markdown("""
<style>
    .stButton>button {
        background-color: #0066CC;
        color: white;
        border-radius: 5px;
        border: none;
        padding: 0.5rem 1rem;
        font-weight: 500;
    }
    .stButton>button:hover {
        background-color: #0052A3;
        color: white;
    }
    .match-badge {
        background-color: #0066CC;
        color: white;
        padding: 0.25rem 0.75rem;
        border-radius: 15px;
        font-weight: bold;
        font-size: 0.9rem;
    }
    .skill-tag {
        background-color: #E3F2FD;
        color: #0066CC;
        padding: 0.25rem 0.5rem;
        border-radius: 10px;
        font-size: 0.85rem;
        display: inline-block;
        margin: 0.2rem;
    }
    .gap-tag {
        background-color: #FFF3E0;
        color: #E65100;
        padding: 0.25rem 0.5rem;
        border-radius: 10px;
        font-size: 0.85rem;
        display: inline-block;
        margin: 0.2rem;
    }
    .candidate-card {
        border: 1px solid #E0E0E0;
        border-radius: 8px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        background-color: #FAFAFA;
    }
    .course-card {
        border-left: 3px solid #0066CC;
        padding: 1rem;
        margin: 0.5rem 0;
        background-color: white;
        border-radius: 4px;
    }
    .ai-status {
        color: #4CAF50;
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'results' not in st.session_state:
    st.session_state.results = None
if 'orchestrator' not in st.session_state:
    st.session_state.orchestrator = None
if 'processing' not in st.session_state:
    st.session_state.processing = False


@st.cache_resource
def initialize_services():
    """Initialize services (cached)"""
    try:
        config = Config()
        
        if not config.is_configured:
            st.error("❌ Missing required configuration. Please set environment variables.")
            st.stop()
        
        db_manager = DatabaseManager(config.db_connection_string)
        bedrock_client = BedrockClient(
            region_name=config.aws_region,
            model_id=config.bedrock_model_id
        )
        orchestrator_instance = orchestrator(db_manager, bedrock_client, config)
        
        return orchestrator_instance, config, db_manager
    except Exception as e:
        st.error(f"❌ Error initializing services: {str(e)}")
        st.stop()


def display_candidate_card(candidate: Dict[str, Any], index: int):
    """Display a candidate result card in the new format"""
    match_pct = int(candidate.get("match_percentage", 0))
    name = candidate.get("name", "Unknown")
    
    # Candidate card container
    st.markdown(f'<div class="candidate-card">', unsafe_allow_html=True)
    
    # Header with name and match percentage
    col_header1, col_header2 = st.columns([3, 1])
    with col_header1:
        st.markdown(f"### {name}")
    with col_header2:
        st.markdown(f'<div class="match-badge">{match_pct}% match</div>', unsafe_allow_html=True)
    
    # Matching Skills
    matched_skills = candidate.get("matched_skills", [])
    if matched_skills:
        st.markdown("**Matching Skills:**")
        skills_html = " ".join([f'<span class="skill-tag">{skill}</span>' for skill in matched_skills[:10]])
        st.markdown(skills_html, unsafe_allow_html=True)
    
    # Skill Gaps
    gaps = candidate.get("gaps", [])
    gap_skills = []
    if gaps:
        for gap in gaps:
            skill = gap.get("skill", "")
            if skill:
                gap_skills.append(skill)
    
    if gap_skills:
        st.markdown("**Skill Gaps:**")
        gaps_html = " ".join([f'<span class="gap-tag">{gap}</span>' for gap in gap_skills[:10]])
        st.markdown(gaps_html, unsafe_allow_html=True)
    
    # Description
    description = candidate.get("description", "")
    if not description:
        # Generate description from match quality and skills
        match_quality = candidate.get("match_quality", "moderate")
        skill_count = len(matched_skills)
        
        if match_quality == "strong":
            description = f"Strong match with {skill_count} matching skills."
        elif match_quality == "moderate":
            description = f"Moderate match with {skill_count} matching skills."
        else:
            description = f"Basic match with {skill_count} matching skills."
        
        if gap_skills:
            gap_count = len(gap_skills)
            if gap_count == 1:
                description += f" Needs upskilling in {gap_skills[0]}."
            else:
                description += f" Needs upskilling in {gap_count} areas."
        else:
            description += " No significant skill gaps identified."
    
    st.markdown(f"*{description}*")
    
    # Recommended Training Courses (max 3) - numbered list, single line spacing
    recommended_courses = candidate.get("recommended_courses", [])
    if recommended_courses:
        st.markdown("**Recommended Training Courses:**")
        for idx, course in enumerate(recommended_courses[:2], 1):
            course_title = course.get("title", "Unknown Course")
            course_desc = course.get("description", "")
            course_rationale = course.get("rationale", "")
            course_level = course.get("level", "N/A")
            course_url = course.get("url", "")
            
            # Use rationale if available, otherwise use description
            display_text = course_rationale if course_rationale else course_desc
            if not display_text:
                display_text = "No description available"
            
            # Make title clickable if URL exists
            if course_url:
                title_html = f'<a href="{course_url}" target="_blank" style="color: #0066CC; text-decoration: none; font-weight: bold;">{course_title}</a>'
            else:
                title_html = f"<strong>{course_title}</strong>"
            
            # Single line format: "1. Title - Description - Level"
            st.markdown(
                f'<div style="margin: 0.2rem 0; line-height: 1.4;">'
                f'<strong>{idx}.</strong> {title_html} - <em>{display_text[:100]}{"..." if len(display_text) > 100 else ""}</em> - Level: {course_level}'
                f'</div>',
                unsafe_allow_html=True
            )
    else:
        # Show message if no courses recommended
        st.markdown("*No training courses recommended at this time.*")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Approve & Request Allocation button
    if st.button("Approve & Request Allocation", key=f"allocate_{index}", type="primary"):
        st.session_state[f"show_form_{index}"] = True


def show_allocation_form(candidate: Dict[str, Any], index: int):
    """Show allocation form in a modal-like container"""
    if not st.session_state.get(f"show_form_{index}", False):
        return
    
    st.markdown("---")
    with st.form(key=f"allocation_form_{index}"):
        st.markdown(f"### Allocation Request: {candidate.get('name', 'Unknown')}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            emp_code = st.text_input("Employee Code *", key=f"emp_code_{index}")
            emp_name = st.text_input("Employee Name *", key=f"emp_name_{index}")
            client_name = st.text_input("Client Name *", key=f"client_name_{index}")
            project_name = st.text_input("Project Name *", key=f"project_name_{index}")
            project_id = st.text_input("Project ID *", key=f"project_id_{index}")
            sow_cr_id = st.text_input("SOW/CR ID *", key=f"sow_cr_id_{index}")
        
        with col2:
            role = st.text_input("Role *", key=f"role_{index}")
            rate = st.number_input("Rate *", min_value=0.0, step=0.01, key=f"rate_{index}")
            allocation_category = st.text_input("Allocation Category *", key=f"allocation_category_{index}")
            allocation_percentage = st.number_input("Allocation % *", min_value=0.0, max_value=100.0, step=0.1, key=f"allocation_percentage_{index}")
            start_date = st.date_input("Start Date *", key=f"start_date_{index}")
            end_date = st.date_input("End Date *", key=f"end_date_{index}")
            rr_id = st.text_input("RR ID *", key=f"rr_id_{index}")
        
        col_submit, col_cancel = st.columns(2)
        with col_submit:
            submitted = st.form_submit_button("Submit Allocation Request", type="primary", use_container_width=True)
        with col_cancel:
            cancel = st.form_submit_button("Cancel", use_container_width=True)
        
        if cancel:
            st.session_state[f"show_form_{index}"] = False
            st.rerun()
        
        if submitted:
            # Validate all fields are filled
            required_fields = {
                "emp_code": emp_code,
                "emp_name": emp_name,
                "client_name": client_name,
                "project_name": project_name,
                "project_id": project_id,
                "sow_cr_id": sow_cr_id,
                "role": role,
                "rate": rate,
                "allocation_category": allocation_category,
                "allocation_percentage": allocation_percentage,
                "start_date": start_date,
                "end_date": end_date,
                "rr_id": rr_id
            }
            
            missing_fields = [field for field, value in required_fields.items() if not value]
            
            if missing_fields:
                st.error(f"Please fill in all required fields: {', '.join(missing_fields)}")
            else:
                # Create allocation request
                try:
                    orchestrator_instance, config, db_manager = initialize_services()
                    email_service = EmailService(config)
                    
                    # Get requirement text from session
                    requirement_text = st.session_state.results.get("requirement_text", "")
                    
                    # Create allocation request object
                    allocation_request = AllocationRequest(
                        emp_code=emp_code,
                        emp_name=emp_name,
                        client_name=client_name,
                        project_name=project_name,
                        project_id=project_id,
                        sow_cr_id=sow_cr_id,
                        role=role,
                        rate=float(rate),
                        allocation_category=allocation_category,
                        allocation_percentage=float(allocation_percentage),
                        start_date=start_date,
                        end_date=end_date,
                        rr_id=rr_id,
                        candidate_id=candidate.get("id", 0),
                        requirement_text=requirement_text,
                        match_score=candidate.get("match_percentage", 0)
                    )
                    
                    # Store in database
                    user_details = allocation_request.to_dict()
                    query = """
                        INSERT INTO allocation_requests 
                            (candidate_id, requirement_text, match_score, user_details, status)
                        VALUES (%s, %s, %s, %s::jsonb, 'pending')
                        RETURNING id
                    """
                    result = db_manager.execute_query(
                        query,
                        params=(
                            allocation_request.candidate_id,
                            allocation_request.requirement_text,
                            allocation_request.match_score,
                            json.dumps(user_details)
                        ),
                        fetch_one=True
                    )
                    
                    if result:
                        allocation_id = result.get("id")
                        
                        # Send emails
                        allocation_dict = {
                            "user_details": user_details,
                            "requirement_text": requirement_text,
                            "match_score": allocation_request.match_score
                        }
                        
                        # Email to admin
                        email_service.send_allocation_email_to_admin(allocation_dict, candidate)
                        
                        # Email to associate with training recommendations
                        recommended_courses = candidate.get("recommended_courses", [])
                        if recommended_courses:
                            email_service.send_training_email_to_associate(
                                candidate.get("email", ""),
                                candidate.get("name", ""),
                                recommended_courses
                            )
                        
                        st.success(f"✅ Allocation request submitted successfully! (ID: {allocation_id})")
                        st.info("📧 Emails have been sent to admin and associate.")
                        st.session_state[f"show_form_{index}"] = False
                        st.rerun()
                    else:
                        st.error("❌ Failed to store allocation request.")
                
                except Exception as e:
                    st.error(f"❌ Error submitting allocation request: {str(e)}")


def main():
    """Main application with two-column layout"""
    # Initialize services
    try:
        orchestrator_instance, config, db_manager = initialize_services()
        st.session_state.orchestrator = orchestrator_instance
    except Exception as e:
        st.error(f"❌ Error initializing: {str(e)}")
        st.stop()
    
    # Logo and title section - logo on left, title on right
    col_logo, col_title = st.columns([1, 4])
    
    with col_logo:
        # Try to load logo using st.image (more reliable) - smaller size
        try:
            import os
            logo_paths = [
                "assets/logo.png",
                "assets/logo.jpg",
                "assets/logo.svg",
                "logo.png",
                "logo.jpg",
                "logo.svg"
            ]
            logo_found = False
            for logo_path in logo_paths:
                if os.path.exists(logo_path):
                    st.image(logo_path, use_container_width=False, width=80)
                    logo_found = True
                    break
            
            if not logo_found:
                # Don't show anything if logo not found
                st.empty()
        except Exception as e:
            # If image loading fails, show nothing
            st.empty()
    
    with col_title:
        # Title with blue color - larger font size to match logo height
        st.markdown(
            '<h1 style="color: #0066CC !important; font-size: 4.5rem !important; font-weight: 700 !important; margin: 0 !important; padding: 0 !important; line-height: 1.2;">AI Demand Hub</h1>',
            unsafe_allow_html=True
        )
    
    # Two-column layout
    col_left, col_right = st.columns([1, 1], gap="large")
    
    # LEFT COLUMN: Chat/Input Panel
    with col_left:
        st.markdown("""
        I've analyzed our internal talent pool and can find the best matching candidates 
        for your role. Paste your job description below and I'll provide candidate 
        recommendations with fitment scores and upskilling plans.
        """)
        
        st.markdown("### Job Description")
        # Initialize requirement_text in session state if not exists
        if "requirement_text" not in st.session_state:
            st.session_state.requirement_text = ""
        
        # Only update session state requirement_text if not processing to avoid duplicates
        if not st.session_state.processing:
            requirement_text = st.text_area(
                "Paste Job Description or Requirements",
                height=200,
                placeholder="e.g., java full stack developer with react experience, 5+ year experience is required",
                key="requirement_input",
                label_visibility="collapsed",
                disabled=False,
                value=st.session_state.get("requirement_text", "")
            )
            # Update session state when text changes
            st.session_state.requirement_text = requirement_text
        else:
            # During processing, show disabled text area with current value
            requirement_text = st.text_area(
                "Paste Job Description or Requirements",
                height=200,
                placeholder="e.g., java full stack developer with react experience, 5+ year experience is required",
                key="requirement_input",
                label_visibility="collapsed",
                disabled=True,
                value=st.session_state.get("requirement_text", "")
            )
        
        st.markdown("### Key Skills (Optional)")
        key_skills = st.text_input(
            "React, Node.js, TypeScript...",
            placeholder="React, Node.js, TypeScript...",
            key="key_skills_input",
            label_visibility="collapsed",
            disabled=st.session_state.processing
        )
        
        # Button container with Find and Reset buttons - right aligned, equal size
        col_spacer, col_find, col_reset = st.columns([2, 1, 1])
        
        with col_spacer:
            # Empty spacer to push buttons to the right
            st.empty()
        
        with col_find:
            # Find candidates button - disabled during processing
            find_clicked = st.button(
                "Find Internal Candidates", 
                type="primary", 
                width="stretch",
                disabled=st.session_state.processing,
                key="find_candidates_btn"
            )
        
        with col_reset:
            # Reset button - disabled during processing
            reset_clicked = st.button(
                "Reset", 
                width="stretch",
                disabled=st.session_state.processing,
                key="reset_btn"
            )
        
        # Handle reset button click
        if reset_clicked and not st.session_state.processing:
            # Clear all session state related to search
            st.session_state.requirement_text = ""
            st.session_state.results = None
            st.session_state.messages = []
            st.session_state.processing = False
            # Clear the text area by rerunning
            st.rerun()
        
        # Handle find candidates button click
        if find_clicked and not st.session_state.processing:
            if not requirement_text.strip():
                st.warning("⚠️ Please enter a job description before searching.")
            else:
                # Clear old results when starting new search
                st.session_state.results = None
                st.session_state.messages = []
                # Set processing flag
                st.session_state.processing = True
                st.rerun()
        
        # Process requirement if processing flag is set
        # Use requirement_text from session state to avoid issues during rerun
        current_requirement = st.session_state.get("requirement_text", "")
        if st.session_state.processing and current_requirement.strip():
            try:
                with st.spinner("🔍 Analyzing talent pool..."):
                    # Process requirement through orchestrator
                    results = orchestrator_instance.process_requirement(current_requirement)
                    # Store results in session state
                    st.session_state.results = results
                    # Store requirement text in results for later use
                    if results:
                        results["requirement_text"] = current_requirement
                    # Add user message
                    st.session_state.messages.append({
                        "role": "user",
                        "content": current_requirement
                    })
                    # Clear processing flag
                    st.session_state.processing = False
                    # Force rerun to display results
                    st.rerun()
            except Exception as e:
                # Clear processing flag on error
                st.session_state.processing = False
                st.error(f"❌ Error processing requirement: {str(e)}")
                import traceback
                st.code(traceback.format_exc())
                # Don't rerun on error, let user see the error
    
    # RIGHT COLUMN: Results Panel
    with col_right:
        # AI Assistant Status
        st.markdown('<div class="ai-status">🟢 AI Assistant Active</div>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Display chat messages
        if st.session_state.messages:
            for msg in st.session_state.messages:
                if msg["role"] == "user":
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    st.markdown(f'<div style="text-align: right; color: #666; font-size: 0.85rem;">{timestamp}</div>', unsafe_allow_html=True)
                    st.markdown(f'**You:** {msg["content"]}')
                    st.markdown("<br>", unsafe_allow_html=True)
        
        # Display results
        if st.session_state.results:
            results = st.session_state.results
            candidates = results.get("candidates", [])
            
            # Note: Candidates are already filtered by match percentage in orchestrator
            # Just limit to max 3 candidates for display
            candidates = candidates[:3] if candidates else []
            
            # Debug output (can be removed later)
            if not candidates and results:
                st.warning(f"⚠️ Debug: Found results object with keys: {list(results.keys())}, but candidates list is empty or None")
            
            if candidates:
                timestamp = datetime.now().strftime("%H:%M:%S")
                st.markdown(f'<div style="text-align: right; color: #666; font-size: 0.85rem;">{timestamp}</div>', unsafe_allow_html=True)
                st.markdown(f"""
                I've analyzed our internal talent pool and found {len(candidates)} matching 
                professional(s). Here are the candidates ranked by fitment score:
                """)
                
                # Display each candidate
                for i, candidate in enumerate(candidates):
                    display_candidate_card(candidate, i)
                    show_allocation_form(candidate, i)
            else:
                timestamp = datetime.now().strftime("%H:%M:%S")
                st.markdown(f'<div style="text-align: right; color: #666; font-size: 0.85rem;">{timestamp}</div>', unsafe_allow_html=True)
                st.markdown("""
                I've analyzed our internal talent pool, but couldn't find any suitable 
                candidates matching your requirements.
                """)
                st.markdown("<br>", unsafe_allow_html=True)
                st.info("💡 **No suitable candidate found.** Please try adjusting your job description or key skills.")
        else:
            # Initial AI message
            timestamp = datetime.now().strftime("%H:%M:%S")
            st.markdown(f'<div style="text-align: right; color: #666; font-size: 0.85rem;">{timestamp}</div>', unsafe_allow_html=True)
            st.markdown("""
            I've analyzed our internal talent pool and can find the best matching candidates 
            for your role. Paste your job description below and I'll provide candidate 
            recommendations with fitment scores and upskilling plans.
            """)
            st.markdown("<br>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()

