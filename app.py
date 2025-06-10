import requests
from dash import Dash, dcc, html, Input, Output, State
import plotly.graph_objs as go
from datetime import date, timedelta

# Initialize the app
app = Dash(__name__)
server = app.server  # for deployment later

# Layout
app.layout = html.Div([
    html.H2("Fitbit & Atmotube Viewer"),

    dcc.ConfirmDialog(
        id='errordialog',
        message="Something went wrong. Check your token and try again."
    ),
    dcc.DatePickerSingle(
        id='date-picker',
        display_format='DD.MM.YYYY',
        max_date_allowed=date.today(),
        min_date_allowed=date.today() - timedelta(days=90),
        date=date.today()
    ),
    
    dcc.Input(
        id='fitbit-token',
        type='text',
        placeholder='Paste Fitbit Access Token here',
        style={'width': '100%', 'margin-top': '10px'}
    ),

    html.Button(
        'Submit', 
        id='submit-button', 
        n_clicks=0, 
        style={'margin-top': '10px'}
    ),

    dcc.Loading(
        id="loading-graph",
        children=[
            dcc.Graph(id='graph-heart-rate'),
            dcc.Graph(id='graph-steps'),
            dcc.Graph(id='graph-sleep'),
            dcc.Graph(id='graph-activity-minutes'),
            dcc.Graph(id='graph-spo2'),
            dcc.Graph(id='graph-weight')
            ],
        type="circle",
        color="blue",
        style={'margin-top': '20px'}
    ),
])

@app.callback(
    Output('graph-heart-rate', 'figure'),
    Output('graph-steps', 'figure'),
    Output('graph-weight', 'figure'),
    Output('graph-spo2', 'figure'),
    Output('graph-activity-minutes', 'figure'),
    Output('graph-sleep', 'figure'),
    Output('errordialog', 'displayed'),
    Input('submit-button', 'n_clicks'),
    State('fitbit-token', 'value'),
    State('date-picker', 'date'),
    prevent_initial_call=True
)

def fetch_fitbit_data(n_clicks, token, selected_date):
    if not token or not selected_date:
        return go.Figure(), True  # Trigger error dialog

    base_url = "https://api.fitbit.com/1/user/-"
    urls = {
        "heart": f"{base_url}/activities/heart/date/{selected_date}/1d/1min.json",
        "steps": f"{base_url}/activities/steps/date/{selected_date}/1d/1min.json",
        "weight": f"{base_url}/body/log/weight/date/{selected_date}.json",
        "activity": f"{base_url}/activities/date/{selected_date}.json",
        "spo2": f"{base_url}/spo2/date/{selected_date}.json",
        "sleep": f"https://api.fitbit.com/1.2/user/-/sleep/date/{selected_date}.json",
    }

    headers = {"Authorization": f"Bearer {token}"}

    try:
        # --- Fetch heart rate ---
        response_hr = requests.get(urls["heart"], headers=headers)
        if response_hr.status_code != 200:
            raise Exception("Heart rate request failed")

        # Extract heart rate intraday values
        hr_data = response_hr.json()
        hr_series = hr_data["activities-heart-intraday"]["dataset"]

        if hr_series:
            x_hr = [dp["time"] for dp in hr_series]
            y_hr = [dp["value"] for dp in hr_series]
            # Plotly heart rate line chart
            fig_hr = go.Figure()
            fig_hr.add_trace(go.Scatter(x=x_hr, y=y_hr, mode='lines', name='Heart Rate'))
            fig_hr.update_layout(title=f"Heart Rate on {selected_date}", xaxis_title="Time", yaxis_title="BPM")

        else:
            fig_hr.update_layout(title="No Heart Rate Data Available")

        # --- Fetch steps ---
        response_steps = requests.get(urls["steps"], headers=headers)
        if response_steps.status_code != 200:
            raise Exception("Steps request failed")

        steps_data = response_steps.json()
        steps_series = steps_data["activities-steps-intraday"]["dataset"] if "activities-steps-intraday" in steps_data else []
        
        fig_steps = go.Figure()
        if steps_series:
            x_steps = [dp["time"] for dp in steps_series]
            y_steps = [dp["value"] for dp in steps_series]
            fig_steps = go.Figure()
            fig_steps.add_trace(go.Scatter(x=x_steps, y=y_steps, mode='lines', name='Steps'))
            fig_steps.update_layout(title=f"Steps on {selected_date}", xaxis_title="Time", yaxis_title="Steps per Minute")

        else:
            fig_steps.update_layout(title="No Steps Data Available")

        # --- Fetch sleep ---
        response_sleep = requests.get(urls["sleep"], headers=headers)
        if response_sleep.status_code != 200:
            raise Exception("Sleep data request failed")

        sleep_data = response_sleep.json()
        sleep_stages = {"deep": 0, "light": 0, "rem": 0, "wake": 0}
        sleep_series = []  # this will store the time-series points (datetime, stage)

        for record in sleep_data.get("sleep", []):
            if record.get("isMainSleep"):  # only main sleep
                summary = record.get("levels", {}).get("summary", {})
                for stage in sleep_stages:
                    sleep_stages[stage] = summary.get(stage, {}).get("minutes", 0)

                # time series data
                for point in record.get("levels", {}).get("data", []):
                    sleep_series.append((point["dateTime"], point["level"]))

        fig_sleep = go.Figure()

        if sleep_series:
            # Group by stage
            stage_colors = {
                "wake": "red",
                "light": "blue",
                "deep": "purple",
                "rem": "green",
                "asleep": "blue",     # fallback (used in 'classic' mode)
                "restless": "orange"  # fallback (used in 'classic' mode)
            }
            for stage in set([s for _, s in sleep_series]):
                times = [t for t, s in sleep_series if s == stage]
                fig_sleep.add_trace(go.Scatter(
                    x=times, 
                    y=[stage] * len(times),
                    mode="markers",
                    marker=dict(color=stage_colors.get(stage, "gray")),
                    name=stage
                ))

            fig_sleep.update_layout(
                title=f"Sleep Stages on {selected_date}",
                xaxis_title="Time",
                yaxis_title="Stage",
                yaxis=dict(type="category"),
            )
        else:
            fig_sleep.update_layout(title="No Sleep Data Available")

        # --- Fetch activity rate ---
        response_activity = requests.get(urls["activity"], headers=headers)
        if response_activity.status_code != 200:
            raise Exception("Activity request failed")

        activity_data = response_activity.json()
        #print("active minutes data:", activity_data)

        summary = activity_data.get("summary", {})

        if summary:
            activity_labels = ["Sedentary", "Light", "Moderate", "Vigorous"]
            activity_minutes = [
                summary.get("sedentaryMinutes", 0),
                summary.get("lightlyActiveMinutes", 0),
                summary.get("moderatelyActiveMinutes", 0),
                summary.get("veryActiveMinutes", 0)
            ]

            fig_activity = go.Figure()
            fig_activity.add_trace(go.Bar(x=activity_labels, y=activity_minutes, marker_color="green"))
            fig_activity.update_layout(title=f"Activity Minutes on {selected_date}", xaxis_title="Activity Type", yaxis_title="Minutes")
            
        else:
            fig_activity.update_layout(title="No Activity Data Available")

        # --- Fetch weight ---
        response_weight = requests.get(urls["weight"], headers=headers)
        if response_weight.status_code != 200:
            raise Exception("Weight request failed")

        weight_data = response_weight.json()
        weight_series = weight_data["weight-intraday"]["dataset"] if "weight-intraday" in weight_data else []

        fig_weight = go.Figure()
        if weight_series:
            x_weight = [dp["time"] for dp in weight_series]
            y_weight = [dp["value"] for dp in weight_series]
            fig_weight = go.Figure()
            fig_weight.add_trace(go.Scatter(x=x_weight, y=y_weight, mode='lines', name='Weight'))
            fig_weight.update_layout(title=f"weight on {selected_date}", xaxis_title="Time", yaxis_title="Weight")

        else:
            fig_weight.update_layout(title="No Weight Data Available")

        # --- Fetch SPO2 ---
        response_spo2 = requests.get(urls["spo2"], headers=headers)
        if response_spo2.status_code != 200:
            raise Exception("SPO2 request failed")

        spo2_data = response_spo2.json()
        spo2_series = spo2_data["spo2-intraday"]["dataset"] if "spo2-intraday" in spo2_data else []
        
        # --- some prints ---
        #print("heart rate data:", hr_data)
        #print("steps data:", steps_data)
        #print("weight data:", weight_data)
        #print("spo2 data:", spo2_data)
        #print("activity data:", activity_data)

        fig_spo2 = go.Figure()
        if spo2_series:
            x_spo2 = [dp["time"] for dp in spo2_series]
            y_spo2 = [dp["value"] for dp in spo2_series]
            fig_spo2 = go.Figure()
            fig_spo2.add_trace(go.Scatter(x=x_spo2, y=y_spo2, mode='lines', name='SPO2'))
            fig_spo2.update_layout(title=f"SPO2 on {selected_date}", xaxis_title="Time", yaxis_title="spo2 per Minute")

        else:
            fig_spo2.update_layout(title="No SPO2 Data Available")

        '''
        # fitbit api access token = eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiIyMjdHNUwiLCJzdWIiOiJDSEJDMzUiLCJpc3MiOiJGaXRiaXQiLCJ0eXAiOiJhY2Nlc3NfdG9rZW4iLCJzY29wZXMiOiJ3aHIgd3BybyB3bnV0IHdzbGUgd2VjZyB3c29jIHdhY3Qgd294eSB3dGVtIHd3ZWkgd2lybiB3Y2Ygd3NldCB3bG9jIHdyZXMiLCJleHAiOjE3NDk2MzE0NjUsImlhdCI6MTc0OTU0NTA2NX0.UszrS3b2fBuxEvqPCO5qhGhGMjHXyZ_5DVRN_6GOp8A
        # --- atmotube data fetch ---
        # test variables
        api_key = "60b13e9f-cbbe-482d-b581-3447bc3910b8"
        mac_addr = "eb:d7:b4:b4:6b:97"
        selected_date = "2025-05-10"
        headers = {'accept': 'application/json'}

        # Construct URL with parameters
        atmotube_url = (
            f"https://api.atmotube.com/api/v1/data"
            f"?api_key={api_key}"
            f"&mac={mac_addr}"
            f"&order=asc"
            f"&format=json"
            f"&offset=0"
            f"&limit=50"
            f"&start_date={selected_date}"
            f"&end_date={selected_date}"
        )
        
        # Check response
        if response_atmotube.status_code == 200:
            data = response_atmotube.json()
            print("Success:", data)
        else:
            print("Error:", response_atmotube.status_code, response_atmotube.text)

        # Make the GET request
        response_atmotube = requests.get(atmotube_url, headers=headers)

        # Check response
        if response_atmotube.status_code == 200:
            data = response_atmotube.json()
            print("Success:", data)
        else:
            print("Error:", response_atmotube.status_code, response_atmotube.text)
        '''

        return fig_hr, fig_steps, fig_weight, fig_spo2, fig_activity, fig_sleep, False

    except Exception as e:
        print("Error:", e)
        return go.Figure(), True


print("Starting the Dash app...")
print("Press Ctrl+C to stop the server.")

if __name__ == '__main__':
    try:
        app.run(debug=True)
    except KeyboardInterrupt:
        print("\nServer stopped by user")
        os._exit(0) #force exit if regular shutdown fails

