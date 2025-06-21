import dash
from dash import dcc, html, Input, Output
import plotly.graph_objs as go
import numpy as np

app = dash.Dash(__name__)

# Länge der Gesamtstrecke
total_distance = 1000  # Meter

app.layout = html.Div([
    html.H2("Optimale Fahrradübergabe"),
    
    html.Label("Geschwindigkeit zu Fuß (beide):"),
    dcc.Slider(1, 10, step=0.5, value=5, id='walk_speed'),

    html.Label("Geschwindigkeit mit Fahrrad (beide):"),
    dcc.Slider(5, 30, step=1, value=15, id='bike_speed'),

    html.Label("Fahrradübergabepunkt (Meter):"),
    dcc.Slider(100, total_distance - 100, step=10, value=400, id='handover'),

    dcc.Graph(id='time-plot')
])

@app.callback(
    Output('time-plot', 'figure'),
    Input('walk_speed', 'value'),
    Input('bike_speed', 'value'),
    Input('handover', 'value')
)
def update_graph(v_walk, v_bike, handover):
    # Person A fährt bis handover, läuft dann weiter
    t_a_bike = handover / v_bike
    t_a_walk = (total_distance - handover) / v_walk
    t_a_total = t_a_bike + t_a_walk

    # Person B läuft bis handover, fährt dann weiter
    t_b_walk = handover / v_walk
    t_b_bike = (total_distance - handover) / v_bike
    t_b_total = t_b_walk + t_b_bike

    fig = go.Figure()
    fig.add_trace(go.Bar(name='Person A', x=["Zeit"], y=[t_a_total]))
    fig.add_trace(go.Bar(name='Person B', x=["Zeit"], y=[t_b_total]))
    fig.update_layout(title="Gesamtzeit (in Sekunden)", barmode='group')

    return fig

if __name__ == '__main__':
    app.run(debug=False)
