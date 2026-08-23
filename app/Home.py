import datetime
import time
import requests
import streamlit as st
import json



# PAGE CONFIG


st.set_page_config(
    page_title="Course Advisor",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)



# CUSTOM CSS (Balanced Medium-Dark Sidebar)


st.markdown(
    """
    <style>
    .stApp {
        background: #f8fafc;
    }
    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1400px;
    }

    [data-testid="stSidebar"] {
        background: #1e293b !important;
        border-right: 1px solid rgba(255, 255, 255, 0.08);
    }
    /* Light text for everything in the sidebar EXCEPT form controls,
       which keep their own (light) background and need dark text. */
    [data-testid="stSidebar"] *:not(input):not(textarea):not(select) {
        color: #E2E8F0 !important;
    }

    /* FIX: sidebar text input (FastAPI URL) was inheriting the light
       #E2E8F0 text color while sitting on a white input box, making
       the typed text nearly invisible. Force dark text + white bg. */
    [data-testid="stSidebar"] input,
    [data-testid="stSidebar"] textarea,
    [data-testid="stSidebar"] select {
        color: #1A2238 !important;
        background-color: #ffffff !important;
        caret-color: #1A2238 !important;
    }
    [data-testid="stSidebar"] .stTextInput > div > div,
    [data-testid="stSidebar"] [data-baseweb="input"],
    [data-testid="stSidebar"] [data-baseweb="select"] {
        background-color: #ffffff !important;
        border-radius: 8px;
    }
    [data-testid="stSidebar"] input::placeholder {
        color: #94a3b8 !important;
    }

    /* Radio option labels sit directly on the dark sidebar background,
       so they should stay light (covered by the rule above already). */


    /* FIX: catch-all — ANY result rendered in the main content area after
       the "Find Courses" button runs (metrics, alerts, course cards,
       advisor message, JSON viewer, expander text, etc.) must default to
       dark text. Placed before the more specific rules below so those can
       still win for the few elements that need a different color
       (blue course code, green confidence pill, white button/hero text). */
    section[data-testid="stMain"] * {
        color: #1A2238 !important;
        -webkit-text-fill-color: #1A2238 !important;
    }

    /* Student search box */
    section[data-testid="stMain"] textarea {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
        caret-color: #ffffff !important;
        background-color: #272830 !important;
    }

    section[data-testid="stMain"] textarea::placeholder {
        color: #94a3b8 !important;
        -webkit-text-fill-color: #94a3b8 !important;
        opacity: 1 !important;
    }

    div[data-testid="stMetric"] {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.03), 0 8px 10px -6px rgba(0, 0, 0, 0.03);
        transition: all 0.3s ease;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-3px);
        border-color: #2563eb;
    }
    /* FIX: metric text (labels like "Recommendations"/"Violations" AND the
       big numbers/values like "2"/"Required"/"121.81s") were rendering
       white-on-white, invisible until selected. A theme-level style is
       winning on specificity/order, so we force EVERY element inside the
       metric card to dark text with maximum specificity, no exceptions. */
    div[data-testid="stMetric"],
    div[data-testid="stMetric"] *,
    div[data-testid="stMetricLabel"],
    div[data-testid="stMetricLabel"] *,
    div[data-testid="stMetricValue"],
    div[data-testid="stMetricValue"] * {
        color: #1A2238 !important;
        -webkit-text-fill-color: #1A2238 !important;
        opacity: 1 !important;
    }
    div[data-testid="stMetricLabel"] * {
        font-weight: 700 !important;
    }
    div[data-testid="stMetricValue"] * {
        font-weight: 800 !important;
    }


    .course-card {
        background: white;
        padding: 24px;
        border-radius: 20px;
        border: 1px solid #e2e8f0;
        margin-bottom: 18px;
        box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.04);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        overflow: hidden;
    }
    .course-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 5px;
        height: 100%;
        background: linear-gradient(to bottom, #2563eb, #d4a373);
    }
    .course-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 20px 35px -15px rgba(37, 99, 235, 0.15);
        border-color: #2563eb;
    }
    section[data-testid="stMain"] .course-code,
    section[data-testid="stMain"] .course-code * {
        color: #2563eb !important;
        -webkit-text-fill-color: #2563eb !important;
        font-size: 13px;
        font-weight: 800;
        letter-spacing: 1px;
        text-transform: uppercase;
    }
    section[data-testid="stMain"] .course-title,
    section[data-testid="stMain"] .course-title * {
        color: #1A2238 !important;
        -webkit-text-fill-color: #1A2238 !important;
        font-size: 20px;
        font-weight: 750;
        margin-top: 6px;
        margin-bottom: 8px;
    }
    section[data-testid="stMain"] .confidence,
    section[data-testid="stMain"] .confidence * {
        color: #10b981 !important;
        -webkit-text-fill-color: #10b981 !important;
        font-weight: 700;
        font-size: 13px;
        background: #ecfdf5;
        padding: 4px 10px;
        border-radius: 20px;
        display: inline-block;
    }

    section[data-testid="stMain"] .stButton > button,
    section[data-testid="stMain"] .stButton > button * {
        background: linear-gradient(135deg, #2563eb 0%, #d4a373 100%) !important;
        color: white !important;
        -webkit-text-fill-color: white !important;
        border: none !important;
        border-radius: 14px;
        font-weight: 700;
        min-height: 48px;
        box-shadow: 0 4px 15px rgba(37, 99, 235, 0.25);
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        opacity: 0.95;
        box-shadow: 0 6px 20px rgba(37, 99, 235, 0.4);
        transform: translateY(-1px);
    }

    /* FIX: headings and alert text (st.subheader, st.warning, st.info,
       st.success, st.error) were rendering white/light — inherited from
       a dark base theme — and were unreadable against the light page
       background and pale alert boxes. Force dark text in the main
       content area. The sidebar keeps its own light-on-dark rules above. */
    section[data-testid="stMain"] h1,
    section[data-testid="stMain"] h2,
    section[data-testid="stMain"] h3,
    section[data-testid="stMain"] h4,
    section[data-testid="stMain"] h5,
    section[data-testid="stMain"] h6 {
        color: #1A2238 !important;
    }
    /* Exception: the hero banner's own heading must stay white — it sits
       on a dark blue/gold gradient, not the page background. */
    section[data-testid="stMain"] .hero-banner,
    section[data-testid="stMain"] .hero-banner *,
    section[data-testid="stMain"] .hero-banner h1,
    section[data-testid="stMain"] .hero-banner h2,
    section[data-testid="stMain"] .hero-banner h3 {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }
    section[data-testid="stMain"] div[data-testid="stAlert"] p,
    section[data-testid="stMain"] div[data-testid="stAlert"] span,
    section[data-testid="stMain"] div[data-testid="stAlert"] div {
        color: #1A2238 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)



# SESSION STATE


if "last_response" not in st.session_state:
    st.session_state.last_response = None

if "last_query" not in st.session_state:
    st.session_state.last_query = ""

if "last_latency" not in st.session_state:
    st.session_state.last_latency = 0.0

if "eval_metrics" not in st.session_state:  
    st.session_state.eval_metrics = None  

if "eval_error" not in st.session_state:  
    st.session_state.eval_error = None  

# SIDEBAR


with st.sidebar:
    st.markdown("### 🎓 Course Advisor")
    st.markdown("AI-powered academic guidance")

    st.markdown("### ⚙️ Connection")

    api_url = st.text_input(
        "FastAPI URL",
        value="http://127.0.0.1:8000",
    )

    endpoint = f"{api_url.rstrip('/')}/advise"

    st.divider()

    st.markdown("### 🧭 Navigation")

    page = st.radio(
        "Go to",
        [
            "🎓 Advisor",
            "📊 Evaluation",
            "🛡️ Security",
            "💰 Observability",
        ],
        label_visibility="collapsed",
    )

    st.divider()

    st.markdown(
        """
        <div style="font-size: 13px; opacity: 0.75; line-height: 1.6;">
            <strong>Course Advisor</strong><br>
            Multi-Agent Academic Recommendation System<br><br>
            <em>Streamlit • FastAPI • LangGraph</em>
        </div>
        """,
        unsafe_allow_html=True,
    )



# API CALL


def call_advisor_stream(query: str, status_container):

    start_time = time.perf_counter()

    try:

        response = requests.post(
            f"{api_url.rstrip('/')}/advise/stream",
            json={"query": query},
            timeout=120,
            stream=True,
        )

        response.raise_for_status()

        final_response = None
        thread_id = None

        for line in response.iter_lines(
            decode_unicode=True
        ):

            if not line:
                continue

            if not line.startswith("data:"):
                continue

            raw_data = line[5:].strip()

            try:
                event = json.loads(raw_data)
            except json.JSONDecodeError:
                continue

            event_type = event.get("type")
            message = event.get("message", "")
            event_data = event.get("data", {})

            
            # START
            

            if event_type == "start":

                thread_id = event_data.get(
                    "thread_id"
                )

                status_container.write(
                    message
                )

            
            # NODE / PROGRESS
            

            elif event_type == "node":

                status_container.write(
                    message
                )

            
            # COMPLETE
            

            elif event_type == "complete":

                status_container.write(
                    message
                )

            
            # HUMAN REVIEW
            

            elif event_type == "human_review":

                status_container.warning(
                    message
                )

                if event_data.get(
                    "thread_id"
                ):
                    thread_id = event_data[
                        "thread_id"
                    ]

            
            # FINAL RESPONSE
            

            elif event_type == "final":

                final_response = event_data.get(
                    "response"
                )

                status_container.success(
                    message
                )

            
            # ERROR
            

            elif event_type == "error":

                return (
                    None,
                    time.perf_counter() - start_time,
                    message,
                    thread_id,
                )

        latency = (
            time.perf_counter()
            - start_time
        )

        return (
            final_response,
            latency,
            None,
            thread_id,
        )

    except requests.exceptions.ConnectionError:

        return (
            None,
            time.perf_counter() - start_time,
            "Could not connect to FastAPI.",
            None,
        )

    except requests.exceptions.Timeout:

        return (
            None,
            time.perf_counter() - start_time,
            "The request timed out.",
            None,
        )

    except requests.exceptions.HTTPError as error:

        return (
            None,
            time.perf_counter() - start_time,
            f"FastAPI returned an error: {error}",
            None,
        )

    except Exception as error:

        return (
            None,
            time.perf_counter() - start_time,
            f"Unexpected error: {error}",
            None,
        )






# def clean_course_title(code: str, title) -> str:
#     """The backend sometimes returns a missing/None title (which renders
#     as the literal string 'null'/'None' once serialized). Fall back to
#     showing the course code itself instead of that placeholder text."""
#     if title is None:
#         return code or "Unknown Course"

#     title_str = str(title).strip()

#     if title_str == "" or title_str.lower() in ("null", "none", "undefined"):
#         return code or "Unknown Course"

#     return title_str

import os


# COURSE CATALOG LOOKUP


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

KNOWLEDGE_BASE_DIR = os.path.join(
    BASE_DIR,
    "data",
    "knowledge_base"
)

CATALOG_PATH = os.path.join(
    KNOWLEDGE_BASE_DIR,
    "catalog.json"
)

DESCRIPTIONS_PATH = os.path.join(
    KNOWLEDGE_BASE_DIR,
    "descriptions.json"
)


def load_json_file(path):

    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)

    except Exception:
        return None


COURSE_CATALOG = load_json_file(CATALOG_PATH)
COURSE_DESCRIPTIONS = load_json_file(DESCRIPTIONS_PATH)


def find_course_title_in_data(data, course_code):

    if data is None:
        return None

    course_code = str(course_code).strip().upper()

    # Dictionary
    if isinstance(data, dict):

        # Example:
        # {
        #     "CS285": {
        #         "title": "..."
        #     }
        # }

        for key, value in data.items():

            if str(key).strip().upper() == course_code:

                if isinstance(value, str):
                    return value.strip()

                if isinstance(value, dict):

                    for title_key in [
                        "course_title",
                        "title",
                        "name",
                        "course_name",
                    ]:

                        title = value.get(title_key)

                        if title:
                            return str(title).strip()

        # Search recursively
        for value in data.values():

            result = find_course_title_in_data(
                value,
                course_code
            )

            if result:
                return result

    # List
    elif isinstance(data, list):

        for item in data:

            if isinstance(item, dict):

                item_code = None

                for code_key in [
                    "course_code",
                    "code",
                    "courseCode",
                    "course_id",
                    "id",
                ]:

                    if code_key in item:

                        item_code = item.get(code_key)

                        if item_code is not None:
                            item_code = str(
                                item_code
                            ).strip().upper()

                            if item_code == course_code:

                                for title_key in [
                                    "course_title",
                                    "title",
                                    "name",
                                    "course_name",
                                    "courseName",
                                ]:

                                    title = item.get(
                                        title_key
                                    )

                                    if title:
                                        return str(
                                            title
                                        ).strip()

                result = find_course_title_in_data(
                    item,
                    course_code
                )

                if result:
                    return result

    return None


def clean_course_title(code, title=None):

    code = str(code).strip().upper()

    # 1. Try title returned by API
    if title is not None:

        title = str(title).strip()

        if title and title.lower() not in [
            "null",
            "none",
            "undefined",
            "unknown",
        ]:

            return title

    # 2. Search catalog.json
    title_from_catalog = find_course_title_in_data(
        COURSE_CATALOG,
        code
    )

    if title_from_catalog:
        return title_from_catalog

    # 3. Search descriptions.json
    title_from_description = find_course_title_in_data(
        COURSE_DESCRIPTIONS,
        code
    )

    if title_from_description:
        return title_from_description

    # 4. Last fallback
    return code


# MARKDOWN EXPORT


def build_markdown(query, data):
    lines = []

    lines.append("# Course Advisor Recommendation")
    lines.append("")
    lines.append(f"**Student Request:** {query}")
    lines.append("")
    lines.append(f"**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    lines.append("## Recommendations")
    lines.append("")

    recommendations = data.get("recommendations", [])

    if not recommendations:
        lines.append("No courses were recommended.")
    else:
        for rec in recommendations:
            code = rec.get("course_code", "Unknown")
            title = clean_course_title(code, rec.get("course_title"))
            confidence = rec.get("confidence", 0)

            lines.append(f"### {code} — {title}")
            lines.append(f"- Confidence: {confidence:.0%}")

            satisfies = rec.get("satisfies", [])
            if satisfies:
                lines.append("- Why it fits:")
                for reason in satisfies:
                    lines.append(f"  - {reason}")

            lines.append("")

    lines.append("## Constraint Status")
    lines.append("")

    violations = data.get("violations", [])

    if violations:
        lines.append("### Violations")
        for violation in violations:
            lines.append(f"- {violation}")
    else:
        lines.append("No hard-constraint violations reported.")

    lines.append("")
    lines.append(f"**Human Review Required:** {data.get('requires_human_review', False)}")
    lines.append("")

    lines.append("## Advisor Message")
    lines.append("")
    lines.append(data.get("message", "No message returned."))

    return "\n".join(lines)



# ADVISOR PAGE


if page == "🎓 Advisor":


    st.markdown(
        """
        <div class="hero-banner" style="
            background: linear-gradient(135deg, #1A2238 0%, #2563eb 55%, #d4a373 100%);
            padding: 42px 48px;
            border-radius: 24px;
            color: white;
            margin-bottom: 30px;
            box-shadow: 0 15px 35px rgba(37, 99, 235, 0.18);
        ">
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
                <span style="font-size: 32px;">✨</span>
                <h2 style="color: #ffffff !important; font-size: 36px; font-weight: 800; margin: 0;">Smart Course Advisor</h2>
            </div>
            <p style="color: #f1f5f9; font-size: 17px; line-height: 1.6; margin: 0; max-width: 800px; opacity: 0.95;">
                Your intelligent academic assistant. Describe your goals or preferences, and let the multi-agent system analyze prerequisites, constraints, and custom requirements to guide your path.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### 💡 What are you looking to study?")

    query = st.text_area(
        "Student request",
        height=130,
        placeholder=(
            "Example:\n"
            "I want an advanced ML elective. "
            "I have completed CS253 and CS231. "
            "I cannot attend courses at 8 AM."
        ),
        label_visibility="collapsed",
        key="student_query",
    )

    col1, col2 = st.columns([1, 4])

    with col1:
        advise_button = st.button(
            "🚀 Find Courses",
            type="primary",
            use_container_width=True,
        )

    if advise_button:
        if not query.strip():
            st.warning("Please describe what you want to study first.")
        else:
            status_container = st.empty()
            with status_container.container():
                data, latency, error, thread_id = call_advisor_stream(
                    query.strip(),
                    status_container
                )

        if thread_id:   

            st.session_state.last_query = query.strip()
            st.session_state.last_latency = latency

            if error:
                st.session_state.last_response = None
                st.error(error)
            else:
                st.session_state.last_response = data
                st.success(f"✨ Advisor response received successfully in {latency:.2f}s!")

    data = st.session_state.last_response

    if data:
        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader("📊 Advisor Insights")

        recommendations = data.get("recommendations", [])
        violations = data.get("violations", [])
        human_review = data.get("requires_human_review", False)

        c1, c2, c3, c4 = st.columns(4)

        with c1:
            st.metric(label="Recommendations", value=len(recommendations))

        with c2:
            st.metric(label="Violations", value=len(violations))

        with c3:
            st.metric(
                label="Human Review",
                value="Required" if human_review else "Not Required",
            )

        with c4:
            st.metric(label="Latency", value=f"{st.session_state.last_latency:.2f}s")

        if violations:
            st.warning("⚠️ Constraint conflict detected. Some hard constraints were violated. Human advisor review may be required.")
        else:
            st.success("🎉 All recommendations successfully passed constraint validation checks!")

        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader("🎯 Recommended Courses For You")

        if not recommendations:
            st.info("No courses were recommended for this request.")
        else:
            for index, rec in enumerate(recommendations, start=1):
                code = rec.get("course_code", "Unknown")
                title = clean_course_title(code, rec.get("course_title"))
                confidence = rec.get("confidence", 0)
                satisfies = rec.get("satisfies", [])

                st.markdown(
                    f"""
                    <div class="course-card">
                        <div class="course-code">OPTION #{index}</div>
                        <div class="course-title">{title}</div>
                        <div class="confidence">✨ Match Confidence: {confidence:.0%}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                if satisfies:
                    with st.expander("🔍 See why this course fits your profile"):
                        for reason in satisfies:
                            st.markdown(f"• {reason}")

        message = data.get("message", "")
        if message:
            st.markdown("<br>", unsafe_allow_html=True)
            st.subheader("🤖 Advisor Detailed Explanation")
            st.info(message)

        if violations:
            st.markdown("<br>", unsafe_allow_html=True)
            st.subheader("⚠️ Constraint Violations")
            for violation in violations:
                st.warning(violation)

        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader("📥 Export & Tools")

        markdown_report = build_markdown(st.session_state.last_query, data)

        st.download_button(
            label="📄",
            data=markdown_report,
            file_name="course_advisor_result.md",
            mime="text/markdown",
        )

        with st.expander("🛠️ Developer View — Raw API Response"):
            st.json(data)



# EVALUATION PAGE


elif page == "📊 Evaluation":
    st.markdown("### 📊 Evaluation")
    st.write("Measure recommendation quality using the project's evaluation dataset.")
    run_eval = st.button("▶️ Run Evaluation", type="primary")
    
    if run_eval:  
        st.session_state.eval_error = None  
        with st.spinner("Running evaluation pipeline... this re-runs retrieval for every eval query, so it may take a while."):  
            try:  
                eval_response = requests.get(  
                    f"{api_url.rstrip('/')}/evaluation/metrics",  
                    timeout=300,  
                )  
                eval_response.raise_for_status()  
                st.session_state.eval_metrics = eval_response.json()  
            except Exception as exc: 
                st.session_state.eval_metrics = None 
                st.session_state.eval_error = str(exc)  

    if st.session_state.eval_error: 
        st.error(f"❌ Failed to run evaluation: {st.session_state.eval_error}") 

    metrics = st.session_state.eval_metrics 
    st.subheader("Evaluation Metrics")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric(
            "Precision",
            f"{metrics['precision']:.2f}" if metrics else "—", )
    with c2:
        st.metric(
            "Recall",
            f"{metrics['recall']:.2f}" if metrics else "—", )
    with c3:
        st.metric(
            "Hard Violations",
            metrics["hard_constraint_violations"] if metrics else "—",  )

    if metrics:  
        st.caption(  
            f"Evaluated {metrics['total_queries']} / "  
            f"{metrics['total_available_queries']} queries."  
        )  
        st.success("🎉 Evaluation complete.")  
    else:
        st.info("Click \"Run Evaluation\" to score the advisor against the team's evaluation dataset.")   



# SECURITY PAGE


elif page == "🛡️ Security":
    st.markdown("### 🛡️ Security")
    st.write("Test the advisor against poisoned course descriptions and prompt-injection attempts.")

    st.subheader("Security Objective")
    st.info("Course descriptions are treated as data, not instructions.")

    st.subheader("Security Checks")
    checks = [
        "Prompt injection resistance",
        "Prerequisite enforcement",
        "Credit constraint enforcement",
        "Schedule conflict detection",
        "Poisoned description isolation",
    ]

    for check in checks:
        st.checkbox(check, value=False, disabled=True)

    st.caption("Security test results will be connected to the team's red-team evaluation.")



# OBSERVABILITY PAGE


elif page == "💰 Observability":
    st.markdown("### 💰 Cost & Observability")
    st.write("Monitor request latency, token usage, model cost, and system health.")

    st.subheader("Current Session")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Requests", "1" if st.session_state.last_response else "0")
    with c2:
        st.metric("Latency", f"{st.session_state.last_latency:.2f}s")
    with c3:
        st.metric("Tokens", "—")
    with c4:
        st.metric("Estimated Cost", "—")

    st.subheader("Observability")
    st.info("Token usage and model cost will be populated when the backend exposes these metrics.")

    st.markdown(
        """
        ### What this page will monitor
        - ⏱️ Request latency
        - 🔢 Input tokens
        - 🔢 Output tokens
        - 💵 Estimated model cost
        - 🔄 Number of retries
        - 🧠 Agent execution steps
        - ⚠️ Constraint violations
        - 👤 Human-in-the-loop escalations
        """
    )

    st.subheader("TOON vs JSON")
    st.info("The TOON-vs-JSON benchmark will be displayed here once catalog benchmark results are connected.")