import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(page_title="HCBI Dashboard", layout="wide")
st.title("HCBI Dashboard")

uploaded_file = st.file_uploader("Upload Excel file", type="xlsx")

if uploaded_file:
    quiz_details = pd.read_excel(uploaded_file, sheet_name="Quiz Details")
    answers_data = pd.read_excel(uploaded_file, sheet_name="Student Answers Data")

    # Merge for item analysis
    merged = pd.merge(answers_data, quiz_details[['QuestionID', 'ItemOrder', 'Notes']], on="QuestionID", how="left")

    # --- STUDENT SCORES SUMMARY ---
    st.header("📊 Student Scores Summary")
    student_group = answers_data.groupby("Email").agg(
        LastName=("LastName", "first"),
        FirstName=("FirstName", "first"),
        TotalCorrect=("isCorrect", "sum"),
        TotalItems=("isCorrect", "count")
    ).reset_index()
    student_group["%Score"] = round((student_group["TotalCorrect"] / student_group["TotalItems"]) * 100, 2)

    threshold = st.selectbox("Select Score Threshold:", [65, 70, 75, 80], index=1)
    threshold_labels = {
        65: "Hard/Challenging exam",
        70: "Standard (default)",
        75: "Relatively manageable exam",
        80: "Easy exam, mastery expected"
    }
    st.caption(f"Definition: {threshold}% - {threshold_labels[threshold]}")
    
    student_group["Status"] = student_group["%Score"].apply(lambda x: "At Risk" if x < threshold else "Likely to Pass")
    
    # Summary stats box
    col1, col2, col3 = st.columns(3)
    col1.metric("Average Score", f"{student_group['%Score'].mean():.2f}%")
    col2.metric("Likely to Pass Students", (student_group["Status"] == "Likely to Pass").sum())
    col3.metric("At-Risk Students", (student_group["Status"] == "At Risk").sum())

    # Filter view
    status_filter = st.selectbox("Filter by Status", ["All", "Likely to Pass", "At Risk"])
    filtered_students = student_group if status_filter == "All" else student_group[student_group['Status'] == status_filter]
    st.dataframe(filtered_students.reset_index())

    # --- ITEM ANALYSIS ---
    st.header("Item Analysis")

    # Legend
    with st.expander("Mastery Level Legend"):
        st.markdown("""
          - **Low:** If <60% of the class is correct
          - **Moderate:** If 60–79% of the class is correct
          - **High:** If 80–100% of the class is correct
        """)
    
    item_group = merged.groupby("QuestionID").agg(
        ItemOrder=("ItemOrder", "first"),
        Question=("Question", "first"),
        TotalAnswers=("isCorrect", "count"),
        TotalCorrect=("isCorrect", "sum"),
        CountA=("Answer", lambda x: (x == "A").sum()),
        CountB=("Answer", lambda x: (x == "B").sum()),
        CountC=("Answer", lambda x: (x == "C").sum()),
        CountD=("Answer", lambda x: (x == "D").sum())
    ).reset_index()

    item_group['%Correct'] = (item_group['TotalCorrect'] / item_group['TotalAnswers']) * 100
    item_group['%Incorrect'] = 100 - item_group['%Correct']

    def mastery_level(p):
        if p < 60:
            return "Low Level Mastery"
        elif p < 80:
            return "Moderate Level Mastery"
        else:
            return "High Level Mastery"

    item_group['MasteryLevel'] = item_group['%Correct'].apply(mastery_level)

    # Sort by ItemOrder
    item_group.sort_values(by='ItemOrder', inplace=True)

    # Filter by mastery
    mastery_filter = st.selectbox("Filter by Mastery Level", ["All", "Low Level Mastery", "Moderate Level Mastery", "High Level Mastery"])

    filtered_items = item_group.copy()
    if mastery_filter != "All":
        filtered_items = filtered_items[filtered_items['MasteryLevel'] == mastery_filter]

    st.dataframe(filtered_items[['ItemOrder', 'QuestionID', 'CountA', 'CountB', 'CountC', 'CountD', '%Correct', '%Incorrect', 'MasteryLevel']])

    # Summary chart for mastery level
    mastery_summary = item_group['MasteryLevel'].value_counts(normalize=False).reset_index()
    mastery_summary.columns = ['MasteryLevel', 'Count']
    mastery_summary['Percentage'] = (mastery_summary['Count'] / mastery_summary['Count'].sum()) * 100

    bar_fig = px.bar(
        mastery_summary,
        x='Count',
        y='MasteryLevel',
        orientation='h',
        color='MasteryLevel',
        text='Percentage',
        title='Distribution of Mastery Levels',
        color_discrete_sequence=px.colors.qualitative.Plotly
    )
    bar_fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    bar_fig.update_layout(legend=dict(orientation="v", x=1.02, y=1), margin=dict(l=20, r=20, t=40, b=20))
    st.plotly_chart(bar_fig, use_container_width=True)

    # Instructor prompt table
    st.subheader("At-Risk Questions Summary")
    at_risk_questions = item_group[item_group['MasteryLevel'] == 'Low Level Mastery']
    if not at_risk_questions.empty:
        prompts = []
        for _, row in at_risk_questions.iterrows():
            most_chosen = max([(row['CountA'], 'A'), (row['CountB'], 'B'), (row['CountC'], 'C'), (row['CountD'], 'D')], key=lambda x: x[0])
            prompts.append({
                "ItemOrder": row['ItemOrder'],
                "QuestionID": row['QuestionID'],
                "Most Chosen Incorrect Answer": most_chosen[1],
                "Count": most_chosen[0],
                "Question": row['Question']
            })
        prompt_df = pd.DataFrame(prompts)
        st.dataframe(prompt_df)
    else:
        st.success("No low mastery questions detected.")

    

    # --- POINTERS TO REVIEW ---
    st.header("📚 Pointers to Review (Per Student)")

    email_list = student_group["Email"].tolist()
    selected_email = st.selectbox("Select a student email:", email_list)

    student_wrong = merged[(merged["Email"] == selected_email) & (merged["isCorrect"] == 0)]

    if student_wrong.empty:
        st.success("All answers correct for this student!")
    else:
        st.info("These are system-generated review prompts based on individual incorrect responses.")
        st.dataframe(student_wrong[["LastName","FirstName","QuestionID", "Question", "Answer", "Text", "Notes"]])
