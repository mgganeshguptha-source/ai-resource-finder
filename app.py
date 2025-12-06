"""
AI Resource Finder - Streamlit Application
"""

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
        padding: 1.5rem 0;
        margin-bottom: 0;
    }
    .candidate-separator {
        border-top: 1px solid #E0E0E0;
        margin: 1.5rem 0;
    }
    .course-card {
        padding: 1rem;
        margin: 0 0 0.5rem 0;
        background-color: white;
        border-radius: 4px;
    }
    .course-link {
        color: #0066CC;
        text-decoration: underline;
        font-weight: bold;
    }
    .course-link:hover {
        color: #0052A3;
        text-decoration: underline;
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
if 'reset_flag' not in st.session_state:
    st.session_state.reset_flag = False
if 'processing' not in st.session_state:
    st.session_state.processing = False
if 'pending_requirement' not in st.session_state:
    st.session_state.pending_requirement = None


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
    try:
        print(f"🔍 DEBUG: display_candidate_card - Candidate keys: {list(candidate.keys()) if isinstance(candidate, dict) else 'Not a dict'}")
        match_pct = int(candidate.get("match_percentage", 0))
        name = candidate.get("name", "Unknown")
        print(f"🔍 DEBUG: display_candidate_card - Name: {name}, Match: {match_pct}%")
        
        # Candidate card container
        st.markdown(f'<div class="candidate-card">', unsafe_allow_html=True)
        
        # Header with name and match percentage
        col_header1, col_header2 = st.columns([3, 1])
        with col_header1:
            st.markdown(f"### {name}")
        with col_header2:
            st.markdown(f'<div class="match-badge">{match_pct}% match</div>', unsafe_allow_html=True)
        
        # Why this CV is recommended?
        matched_skills = candidate.get("matched_skills", [])
        match_quality = candidate.get("match_quality", "moderate")
        proficiency_insights = candidate.get("proficiency_insights", "")
        experience_summary = candidate.get("experience_summary", "")
        domain_tags = candidate.get("domain_tags", [])
        
        if matched_skills:
            # Generate justification text
            top_skills = matched_skills[:3]  # Top 3 matching skills
            skills_text = ", ".join(top_skills)
            
            # First line: Highlight key skills (without match percentage)
            if match_quality == "strong":
                line1 = f"This candidate demonstrates strong expertise in {skills_text}, making them an excellent fit for this role."
            elif match_quality == "moderate":
                line1 = f"This candidate shows solid proficiency in {skills_text}, aligning well with the role requirements."
            else:
                line1 = f"This candidate has relevant experience in {skills_text}, providing a good foundation for this position."
            
            # Second line: Add experience summary quote, proficiency insights, or domain match
            line2 = ""
            if experience_summary:
                # Use relevant quote from experience summary (limit to 200 chars)
                summary_quote = experience_summary[:200].strip()
                if len(experience_summary) > 200:
                    summary_quote += "..."
                line2 = f" {summary_quote}"
            elif proficiency_insights:
                line2 = f" {proficiency_insights[:150]}{'...' if len(proficiency_insights) > 150 else ''}"
            elif domain_tags:
                line2 = f" The candidate has relevant experience in {', '.join(domain_tags[:2])} domain(s), making them a suitable fit for this role."
            else:
                line2 = " The candidate's skill set aligns well with the job requirements and demonstrates the necessary technical capabilities."
            
            # Combine both lines with full stop
            justification_text = line1 + line2
            
            st.markdown('<h4 style="color: #0066CC; font-size: 1.1em; margin-bottom: 0.5rem;">Why this CV is recommended?</h4>', unsafe_allow_html=True)
            st.markdown(f"{justification_text}")
            st.markdown("<br>", unsafe_allow_html=True)
        
        # What's missing for this role?
        gaps = candidate.get("gaps", [])
        missing_skills = candidate.get("missing_skills", [])
        gap_skills = []
        gap_types = {}
        
        if gaps:
            for gap in gaps:
                skill = gap.get("skill", "")
                gap_type = gap.get("gap_type", "")
                severity = gap.get("severity", "medium")
                if skill:
                    gap_skills.append(skill)
                    gap_types[skill] = {"type": gap_type, "severity": severity}
        
        # Combine missing skills from gaps and missing_skills field
        all_missing = list(set(missing_skills + gap_skills))
        
        if all_missing:
            # Generate description about what's missing (combined into one paragraph)
            top_missing = all_missing[:3]  # Top 3 missing skills
            missing_text = ", ".join(top_missing)
            
            # First line: List missing skills
            if len(all_missing) == 1:
                line1 = f"The candidate lacks {missing_text}, which is a required skill for this role."
            elif len(all_missing) <= 3:
                line1 = f"The candidate is missing key skills including {missing_text}, which are important for this position."
            else:
                line1 = f"The candidate lacks several required skills including {missing_text}, and {len(all_missing) - 3} other skill(s)."
            
            # Second line: Describe the impact or what's needed (continue on same line after full stop)
            high_severity_gaps = [s for s in gap_skills if gap_types.get(s, {}).get("severity") == "high"]
            if high_severity_gaps:
                line2 = f" These gaps, particularly in {', '.join(high_severity_gaps[:2])}, may require additional training or upskilling before full role readiness."
            else:
                line2 = " While these gaps exist, the candidate's overall profile remains viable with appropriate training and onboarding support."
            
            # Combine both lines
            missing_text_combined = line1 + line2
            
            st.markdown('<h4 style="color: #0066CC; font-size: 1.1em; margin-bottom: 0.5rem;">What\'s missing for this role?</h4>', unsafe_allow_html=True)
            st.markdown(f"{missing_text_combined}")
            st.markdown("<br>", unsafe_allow_html=True)
        else:
            # No gaps - show positive message (combined into one paragraph)
            no_gaps_text = "This candidate meets all the key requirements for this role. No significant skill gaps identified - the candidate is well-aligned with the job requirements."
            
            st.markdown('<h4 style="color: #0066CC; font-size: 1.1em; margin-bottom: 0.5rem;">What\'s missing for this role?</h4>', unsafe_allow_html=True)
            st.markdown(f"{no_gaps_text}")
            st.markdown("<br>", unsafe_allow_html=True)
        
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
        # Recommended Training Courses (1-2 courses)
        recommended_courses = candidate.get("recommended_courses", [])
        if recommended_courses:
            st.markdown('<h4 style="color: #0066CC; font-size: 1.1em; margin-top: 0.25rem; margin-bottom: 0; padding-bottom: 0;">Recommended Training Courses:</h4>', unsafe_allow_html=True)
            for course in recommended_courses:
                course_title = course.get("title", "Unknown Course")
                course_url = course.get("url", "")
                course_desc = course.get("description", "")
                course_rationale = course.get("rationale", "")
                # Use rationale if available, otherwise use description
                course_text = course_rationale if course_rationale else course_desc
                if not course_text:
                    course_text = "Recommended to address skill gaps"
                course_level = course.get("level", "N/A")
                
                st.markdown(f'<div class="course-card" style="margin-top: 0 !important;">', unsafe_allow_html=True)
                # Make title a clickable link if URL is available
                if course_url:
                    st.markdown(f'<a href="{course_url}" target="_blank" class="course-link"><strong>{course_title}</strong></a>', unsafe_allow_html=True)
                else:
                    st.markdown(f"**{course_title}**")
                st.markdown(f"*{course_text}*")
                st.markdown(f"Level: {course_level}")
                st.markdown(f'</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Approve & Request Allocation button
        if st.button("Approve & Request Allocation", key=f"allocate_{index}", type="primary"):
            st.session_state[f"show_form_{index}"] = True
    except Exception as e:
        print(f"🔍 DEBUG: Error in display_candidate_card: {str(e)}")
        import traceback
        print(traceback.format_exc())
        st.error(f"❌ Error displaying candidate card: {str(e)}")
        raise


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
    
    # Logo and Title Section
    col_logo, col_title = st.columns([1, 4])
    with col_logo:
        try:
            st.image("assets/logo.png", width=150)
        except:
            pass  # Logo placeholder if image not found
    with col_title:
        st.title("AI Demand Hub")
    
    # Two-column layout
    col_left, col_right = st.columns([1, 1], gap="large")
    
    # LEFT COLUMN: Chat/Input Panel
    with col_left:
        st.markdown("""
        I've analyzed our internal talent pool and can find the best matching candidates 
        for your role. Paste your job description below and I'll provide candidate 
        recommendations with fitment scores and upskilling plans.
        """)
        
        # Handle reset - clear everything BEFORE widgets are created
        if st.session_state.reset_flag:
            # Clear results and messages
            st.session_state.results = None
            st.session_state.messages = []
            # Clear input values in session state before widgets are created
            if 'requirement_input' in st.session_state:
                del st.session_state['requirement_input']
            if 'key_skills_input' in st.session_state:
                del st.session_state['key_skills_input']
            st.session_state.reset_flag = False
            st.rerun()
        
        st.markdown("### Job Description")
        requirement_text = st.text_area(
            "Paste Job Description or Requirements",
            height=200,
            placeholder="e.g., java full stack developer with react experience, 5+ year experience is required",
            key="requirement_input",
            label_visibility="collapsed"
        )
        
        st.markdown("### Key Skills (Optional)")
        key_skills = st.text_input(
            "React, Node.js, TypeScript...",
            placeholder="React, Node.js, TypeScript...",
            key="key_skills_input",
            label_visibility="collapsed"
        )
        
        # Button row: Find Candidates and Reset
        col_find, col_reset = st.columns([2, 1])
        with col_find:
            find_disabled = st.session_state.processing
            if st.button("Find Internal Candidates", type="primary", use_container_width=True, disabled=find_disabled):
                if not requirement_text.strip():
                    st.warning("⚠️ Please enter a job description before searching.")
                else:
                    # Clear right side pane first
                    print(f"🔍 DEBUG: Button clicked - clearing results and setting processing flag")
                    st.session_state.results = None
                    st.session_state.messages = []
                    st.session_state.processing = True
                    # Store requirement text for processing
                    st.session_state.pending_requirement = requirement_text
                    print(f"🔍 DEBUG: About to rerun - processing: {st.session_state.processing}, pending_requirement: {st.session_state.pending_requirement[:50] if st.session_state.pending_requirement else 'None'}")
                    st.rerun()
        
        with col_reset:
            reset_disabled = st.session_state.processing
            if st.button("Reset", use_container_width=True, disabled=reset_disabled):
                # Set reset flag to clear everything
                st.session_state.reset_flag = True
                st.session_state.processing = False
                st.session_state.pending_requirement = None
                st.rerun()
        
        # Process requirement if processing flag is set
        if st.session_state.processing and st.session_state.get('pending_requirement'):
            requirement_to_process = st.session_state.pending_requirement
            print(f"🔍 DEBUG: Processing block entered - requirement: {requirement_to_process[:50]}...")
            with st.spinner("🔍 Analyzing talent pool..."):
                try:
                    # Process requirement through orchestrator
                    print(f"🔍 DEBUG: Calling orchestrator.process_requirement...")
                    results = orchestrator_instance.process_requirement(requirement_to_process)
                    print(f"🔍 DEBUG: Results received. Type: {type(results)}, Keys: {list(results.keys()) if isinstance(results, dict) else 'Not a dict'}")
                    
                    if results and isinstance(results, dict):
                        candidates = results.get("candidates", [])
                        print(f"🔍 DEBUG: Number of candidates in results: {len(candidates)}")
                        for i, c in enumerate(candidates):
                            print(f"🔍 DEBUG: Result candidate {i+1}: {c.get('name', 'Unknown')} - {c.get('match_percentage', 0)}%")
                    
                    # Store results BEFORE clearing processing flag
                    st.session_state.results = results
                    print(f"🔍 DEBUG: Results stored in session_state")
                    print(f"🔍 DEBUG: session_state.results is None: {st.session_state.results is None}")
                    print(f"🔍 DEBUG: session_state.results type: {type(st.session_state.results)}")
                    if st.session_state.results:
                        print(f"🔍 DEBUG: session_state.results has candidates: {len(st.session_state.results.get('candidates', []))}")
                    
                    st.session_state.messages.append({
                        "role": "user",
                        "content": requirement_to_process
                    })
                    # Clear processing flags AFTER storing results
                    st.session_state.processing = False
                    st.session_state.pending_requirement = None
                    print(f"🔍 DEBUG: About to rerun... Processing flag: {st.session_state.processing}")
                    print(f"🔍 DEBUG: Results still in session_state before rerun: {st.session_state.results is not None}")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error processing requirement: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())
                    print(f"🔍 DEBUG: Error occurred: {str(e)}")
                    st.session_state.processing = False
                    st.session_state.pending_requirement = None
                    st.rerun()
        else:
            print(f"🔍 DEBUG: Processing block NOT entered - processing: {st.session_state.processing}, pending_requirement: {st.session_state.get('pending_requirement') is not None}")
    
    # RIGHT COLUMN: Results Panel
    with col_right:
        # Debug info
        print(f"🔍 DEBUG: Right panel - session_state.results exists: {st.session_state.results is not None}")
        print(f"🔍 DEBUG: Right panel - processing flag: {st.session_state.processing}")
        print(f"🔍 DEBUG: Right panel - pending_requirement: {st.session_state.get('pending_requirement') is not None}")
        if st.session_state.results:
            print(f"🔍 DEBUG: Right panel - Results type: {type(st.session_state.results)}")
            if isinstance(st.session_state.results, dict):
                print(f"🔍 DEBUG: Right panel - Results keys: {list(st.session_state.results.keys())}")
                candidates = st.session_state.results.get("candidates", [])
                print(f"🔍 DEBUG: Right panel - Number of candidates: {len(candidates)}")
                if candidates:
                    for i, c in enumerate(candidates):
                        print(f"🔍 DEBUG: Right panel - Candidate {i}: {c.get('name', 'Unknown')} - {c.get('match_percentage', 0)}%")
                        print(f"🔍 DEBUG: Right panel - Candidate {i} keys: {list(c.keys()) if isinstance(c, dict) else 'Not a dict'}")
        
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
            print(f"🔍 DEBUG: Display block - session_state.results exists")
            try:
                results = st.session_state.results
                print(f"🔍 DEBUG: Display block - results type: {type(results)}")
                
                if not isinstance(results, dict):
                    st.error(f"❌ Results is not a dictionary. Type: {type(results)}")
                    return
                
                candidates = results.get("candidates", [])
                print(f"🔍 DEBUG: Display block - Candidates from results: {len(candidates)}")
                
                if not isinstance(candidates, list):
                    st.error(f"❌ Candidates is not a list. Type: {type(candidates)}")
                    return
                
                # Filter candidates with match percentage > 50%
                candidates_filtered = []
                for c in candidates:
                    if not isinstance(c, dict):
                        print(f"🔍 DEBUG: Skipping non-dict candidate: {type(c)}")
                        continue
                    match_pct = c.get("match_percentage", 0)
                    print(f"🔍 DEBUG: Candidate {c.get('name', 'Unknown')} - Match: {match_pct}%")
                    if match_pct > 50:
                        candidates_filtered.append(c)
                
                print(f"🔍 DEBUG: Display block - Candidates after >50% filter: {len(candidates_filtered)}")
                
                # Limit to max 3 candidates
                candidates = candidates_filtered[:3]
                print(f"🔍 DEBUG: Display block - Candidates after limit to 3: {len(candidates)}")
                
                if candidates:
                    print(f"🔍 DEBUG: Display block - About to display {len(candidates)} candidate(s)")
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    st.markdown(f'<div style="text-align: right; color: #666; font-size: 0.85rem;">{timestamp}</div>', unsafe_allow_html=True)
                    st.markdown(f"""
                    I've analyzed our internal talent pool and found {len(candidates)} matching 
                    professional(s). Here are the candidates ranked by fitment score:
                    """)
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    # Display each candidate
                    for i, candidate in enumerate(candidates):
                        print(f"🔍 DEBUG: Display block - Displaying candidate {i+1}: {candidate.get('name', 'Unknown')}")
                        try:
                            display_candidate_card(candidate, i)
                            show_allocation_form(candidate, i)
                            # Add separator line between candidates (not after the last one)
                            if i < len(candidates) - 1:
                                st.markdown('<div class="candidate-separator"></div>', unsafe_allow_html=True)
                        except Exception as e:
                            st.error(f"❌ Error displaying candidate {i+1}: {str(e)}")
                            import traceback
                            st.code(traceback.format_exc())
                            print(f"🔍 DEBUG: Error displaying candidate {i+1}: {str(e)}")
                            print(traceback.format_exc())
                else:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    st.markdown(f'<div style="text-align: right; color: #666; font-size: 0.85rem;">{timestamp}</div>', unsafe_allow_html=True)
                    st.markdown("""
                    I've analyzed our internal talent pool, but couldn't find any suitable 
                    candidates matching your requirements.
                    """)
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.info("💡 **No suitable candidate found.** Please try adjusting your job description or key skills.")
            except Exception as e:
                st.error(f"❌ Error in display block: {str(e)}")
                import traceback
                st.code(traceback.format_exc())
                print(f"🔍 DEBUG: Display block error: {str(e)}")
                print(traceback.format_exc())
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

