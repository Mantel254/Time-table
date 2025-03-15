import os
from flask import Flask, render_template, request, send_file
import pandas as pd
from datetime import datetime
import re
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'

# --- Your same functions for shorten, clean, truncate, truncate_more, create_pdf go here ---
# Make sure to include all helper functions as in your provided code

def shorten(data_path, course):
    import pandas as pd

    # Load data without predefined headers
    data = pd.read_excel(data_path, header=None)

    # Convert all values to strings for safe regex matching
    data = data.astype(str)

    # Define regex patterns for filtering
    bmcs_pattern = course  # Matches "BMCS Y2S2"
    day_pattern = r'(d\s*a\s*y|m\s*o\s*n\s*d\s*a\s*y|t\s*u\s*e\s*s\s*d\s*a\s*y|w\s*e\s*d\s*n\s*e\s*s\s*d\s*a\s*y|t\s*h\s*u\s*r\s*s\s*d\s*a\s*y|f\s*r\s*i\s*d\s*a\s*y)'
    # day_pattern = r'^(day|monday|tuesday|wednesday|thursday|friday)$'  # Matches weekdays
    room_pattern = r'NAME OF ROOM'  # Matches "NAME OF ROOM", case-insensitive
    time_pattern = r'\b\d{1,2}\.\d{2}\b'  # Matches time formats like "8.00", "9.30"

    # Create masks to find matching columns
    mask_bmcs = data.apply(lambda x: x.str.contains(bmcs_pattern, na=False, case=False))
    mask_day = data.apply(lambda x: x.str.contains(day_pattern, na=False, case=False))
    mask_room = data.apply(lambda x: x.str.contains(room_pattern, na=False, case=False))
    mask_time = data.apply(lambda x: x.str.contains(time_pattern, na=False, case=False))

    # Find columns to keep (columns with BMCS Y2S2, "Day", "NAME OF ROOM", or Time)
    columns_to_keep = mask_bmcs.any(axis=0) | mask_day.any(axis=0) | mask_room.any(axis=0) | mask_time.any(axis=0)

    # Find rows to keep (rows containing BMCS Y2S2 or Day)
    rows_to_keep = mask_bmcs.any(axis=1) | mask_day.any(axis=1)

    # Filter the DataFrame to keep only relevant rows & columns
    filtered_data = data.loc[rows_to_keep, columns_to_keep]

    # DO NOT set any row as column headers (keeps numerical column indexing)
    filtered_data = filtered_data.reset_index(drop=True)  # Reset index but keep original column numbers

    # Set first row as column headers
    filtered_data.columns = filtered_data.iloc[0]  # Assign first row as headers

    # Remove the first row from data and reset index
    filtered_data = filtered_data.iloc[1:].reset_index(drop=True)

    return filtered_data

def clean(data):
# Function to normalize days (remove spaces & fix capitalization)
    def clean_day(text):
        text = re.sub(r'\s+', '', text).capitalize()  # Remove spaces & capitalize first letter
        return text if text in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"] else None

    # Normalize the first column (Day of the Week)
    data.iloc[:, 0] = data.iloc[:, 0].astype(str).str.strip().apply(clean_day)

    # Initialize variable to track the current day
    current_day = None

    # Iterate through rows and fill NaN values with the latest valid day
    for index in range(len(data)):
        first_col_value = data.iloc[index, 0]

        # Skip "DAY" separator rows
        if first_col_value == "Day":
            continue

        # If a valid day is found, update current_day
        if first_col_value:
            current_day = first_col_value

        # Replace NaN or empty cells with the last found valid day
        elif pd.isna(first_col_value) or first_col_value == "nan":
            data.iloc[index, 0] = current_day  # Fill missing days with the latest valid one

    # Print cleaned DataFrame
    return data

def truncate(data,course):
    # Define regex pattern for matching 'BSSC Y3S2'
    pattern = course

    # Initialize results list
    matches = []

    # Function to clean extra spaces
    def clean_spaces(text):
        return re.sub(r'\s{2,}', ' ', text.strip())  # Replace 2+ spaces with 1 space

    # Iterate through each row
    for row_idx in range(len(data)):
        for col_idx in range(len(data.columns)):  
            cell_value = str(data.iat[row_idx, col_idx])  # Convert cell to string

            if re.search(pattern, cell_value, re.IGNORECASE):  # Check for regex match
                day_value = clean_spaces(str(data.iat[row_idx, 0]))  # Day column
                room_value = clean_spaces(str(data.iat[row_idx, 1]))  # Room column
                cell_value = clean_spaces(cell_value)  # Matched cell content
                column_header = clean_spaces(str(data.columns[col_idx]))  # Column header
                
                # Format the result
                match_text = f"{day_value} | {room_value} | {cell_value} | {column_header}"
                matches.append(match_text)

    # Print the results
    return matches

def truncate_more(dat):
# Function to clean and normalize time strings
    def clean_time(time_str):
        time_str = time_str.replace(' ', '').lower()
        time_str = re.sub(r'\s*-\s*', '-', time_str)
        time_str = re.sub(r'\.?([ap])\.?m\.?', r'\1m', time_str)
        return time_str

    # Function to convert time to 24-hour format
    def convert_to_24hr(time_str, ref='am'):
        if 'am' not in time_str.lower() and 'pm' not in time_str.lower():
            time_str += ref
        return datetime.strptime(time_str.strip().lower(), "%I.%M%p")

    # Dictionary to hold grouped records (group by day and course only)
    grouped = {}

    # Step 1: Parse and group
    for entry in dat:
        parts = [x.strip() for x in entry.split('|')]
        if len(parts) != 4:
            continue
        day, time_range, course, venue = parts
        time_range = clean_time(time_range)
        start_time_str, end_time_str = map(str.strip, time_range.split('-'))

        # Extract am/pm from end_time to apply to start_time if missing
        am_pm_match = re.search(r'(am|pm)', end_time_str.lower())
        ref_period = am_pm_match.group(1) if am_pm_match else 'am'  # Default to 'am'

        # Convert times to datetime objects
        start_time = convert_to_24hr(start_time_str, ref=ref_period)
        end_time = convert_to_24hr(end_time_str, ref=ref_period)

        # Group by (day, course) and append both time and venue
        key = (day, course)
        if key not in grouped:
            grouped[key] = {'times': [], 'venues': set()}
        grouped[key]['times'].append((start_time, end_time))
        grouped[key]['venues'].add(venue)  # Add venue to set (avoid duplicates)
        # print(f"course:{course},, day:{day}")

    # Step 2: Process each group to find min start, max end, and combine venues
    merged_data = []
    for (day, course), value in grouped.items():
        times = value['times']
        venues = ', '.join(sorted(value['venues']))  # Combine unique venues

        # Find earliest start and latest end time
        earliest_start = min([t[0] for t in times])
        latest_end = max([t[1] for t in times])

        # Format back to time string
        def format_time(dt):
            return dt.strftime("%I.%M%p").lstrip('0').replace('.00', '')  # e.g., 9.00am -> 9am

        final_time = f"{format_time(earliest_start)}-{format_time(latest_end)}"
        merged_row = f"{day} | {final_time} | {course} | {venues}"
        merged_data.append(merged_row)
    return merged_data

def remove_unnecessary(matches):

    final_output = []
    pattern = r'[A-Z]{3}\s*\d{4}\s*:\s*.*'

    # Step 1: Extract the merged rows
    for entry in matches:
        parts = [x.strip() for x in entry.split('|')]
        day, time_range, course, venue = parts
        found = re.search(pattern, course)
        if found:
            matched_course = found.group(0).strip()
            merged_row = f"{day} | {time_range} | {matched_course} | {venue}"
            final_output.append(merged_row)

    # Step 2: Remove duplicates while preserving order
    unique_output = []
    seen = set()
    for row in final_output:
        if row not in seen:
            unique_output.append(row)
            seen.add(row)

    # Step 3: Print final output
    return unique_output

# Update create_pdf to accept filename as parameter
def create_pdf(data_list, filename):
    structured_data = []
    for item in data_list:
        day, time, course, venue = [part.strip() for part in item.split('|')]
        structured_data.append([day, time, course, venue])

    df = pd.DataFrame(structured_data, columns=["Day", "Time", "Course & Lecturer", "Venue"])
    pdf = SimpleDocTemplate(filename, pagesize=landscape(letter))
    table_data = [df.columns.tolist()] + df.values.tolist()
    table = Table(table_data)
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ])
    table.setStyle(style)
    pdf.build([table])


def courses(data_path):
    data = pd.read_excel(data_path, header=None)
    # Regex pattern to match words of format like BMCS Y4S2
    pattern = r'\b[A-Z]+ Y\d+S\d+\b'
    # Iterate over rows and collect all matches into one list
    # List to hold all matches
    all_matches = []

    #  Iterate over each row and each column
    for row in data.itertuples(index=False):
        for cell in row:
            if isinstance(cell, str):  # Ensure it's a string before searching
                matches = re.findall(pattern, cell)
                all_matches.extend(matches)

    unique_matches = list(set(all_matches))

    # print("All Matches:", all_matches)
    # print("Unique Matches:", unique_matches)
    return unique_matches


from flask import Flask, render_template, request, send_file, session
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Needed for session handling
app.config['UPLOAD_FOLDER'] = 'uploads'


@app.route('/', methods=['GET', 'POST'])
def index():
    courses_list = []  # Empty by default

    # print("IN INDEX")  # See if route is hit

    if request.method == 'POST':
        # print("POST REQUEST RECEIVED")
        if 'file' in request.files:
            file = request.files['file']
            # print("AFTER FILE UPLOAD")

            if file.filename != '':
                print("NOT IN EMPTY FILE")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
                
                # Ensure uploads directory exists
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                
                file.save(filepath)
                session['filepath'] = filepath  # Store filepath for second stage

                # Extract courses
                courses_list = courses(filepath)  # Your custom function that extracts course names
                print(f"Extracted courses: {courses_list}")

                # Return page with course dropdown
                return render_template('index.html', courses=courses_list, step=2)

            print("PRINT(EMPTY FILE)")
        elif 'course' in request.form:
            # print("AFTER COURSE SELECTION")
            selected_course = request.form['course']
            filepath = session.get('filepath')  # Retrieve uploaded file
            print(f"FILE PATH=={filepath}")
            if filepath and selected_course:
                # Proceed with the logic using the selected course
                data = shorten(filepath, selected_course)
                data = clean(data)
                match = truncate(data, selected_course)
                dat = remove_unnecessary(match)
                draft = truncate_more(dat)
                print(f"DRAFT=={draft}")
                
                # os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                # print(f"Upload folder is ready: {app.config['UPLOAD_FOLDER']}")
                # # Ensure uploads directory exists before creating the PDF
                # # os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

                # # Output PDF (optionally use unique name to avoid overwriting)
                # output_pdf = os.path.join(app.config['UPLOAD_FOLDER'], 'Timetable.pdf')
                # print(f'THE OUTPUT::{output_pdf}')
                # Create PDF
                
                
                BASE_DIR = os.path.dirname(os.path.abspath(__file__))
                app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                print(f"Upload folder is ready: {app.config['UPLOAD_FOLDER']}")

                # Inside your route or function
                output_pdf = os.path.join(app.config['UPLOAD_FOLDER'], 'Timetable.pdf')
                print(f'THE OUTPUT PDF PATH: {output_pdf}')

                create_pdf(draft, output_pdf)

                # Optional: Check if file exists before sending
                if os.path.exists(output_pdf):
                    return send_file(output_pdf, as_attachment=True)
                else:
                    return "Error: Timetable PDF could not be created.", 500

    # print("PAST IF STATEMENT")  # After GET or empty POST
    return render_template('index.html', courses=courses_list, step=1)  # Initial GET page


if __name__ == '__main__':
    # Ensure upload directory exists on startup based on config
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)
