import math
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Equivalent Performance by Distance!", page_icon="🏃‍♂️", layout="wide"
)

# --- Helper Functions ---
def hhmmss_to_seconds(time_str):
  try:
    parts = list(map(int, time_str.replace(" ", "").split(":")))
    if len(parts) == 3:
      return parts[0] * 3600 + parts[1] * 60 + parts[2]
    elif len(parts) == 2:
      return parts[0] * 60 + parts[1]
    return float(time_str)
  except:
    return None


def seconds_to_hhmmss(seconds):
  seconds = round(seconds)
  hours, minutes, secs = (
      seconds // 3600,
      (seconds % 3600) // 60,
      seconds % 60,
  )
  if hours > 0:
    return f"{hours}h {minutes:02d}m {secs:02d}s"
  return f"{minutes}m {secs:02d}s"


# --- App Header ---
st.title("🏃‍♂️ Equivalent Performance by Distance!")
st.write(
    "A professional performance model powered by 4-point synthetic regression"
    " and proportional log-decay."
)
st.markdown("---")

# --- Sidebar Inputs ---
st.sidebar.header("⚙️ Configuration")
mode = st.sidebar.radio(
    "Calculator Precision Mode:", ["2 Baseline PBs", "3 Baseline PBs (More Precise)"]
)

st.sidebar.markdown("---")
st.sidebar.header("🎯 Target Distance")
target_distance = st.sidebar.number_input(
    "Desired Target Distance (meters)",
    min_value=1500,
    max_value=42195,
    value=5000,
    step=100,
)

st.sidebar.markdown("---")
st.sidebar.header("📋 Baseline Performances")

# PB 1 Inputs
st.sidebar.subheader("Baseline 1 (Short)")
d1 = st.sidebar.number_input(
    "Distance 1 (meters)", min_value=100, value=2000, step=100, key="d1"
)
t1_in = st.sidebar.text_input("Time 1 (H:MM:SS or MM:SS)", value="7:14", key="t1")

# PB 2 Inputs
st.sidebar.subheader("Baseline 2 (Mid)")
d2_min = int(d1 + 100)
d2 = st.sidebar.number_input(
    "Distance 2 (meters)",
    min_value=int(d1 + 1),
    value=max(3000, d2_min),
    step=100,
    key="d2",
)
t2_in = st.sidebar.text_input("Time 2 (H:MM:SS or MM:SS)", value="11:12", key="t2")

if mode == "3 Baseline PBs (More Precise)":
  st.sidebar.subheader("Baseline 3 (Long)")
  d3_min = int(d2 + 100)
  d3 = st.sidebar.number_input(
      "Distance 3 (meters)",
      min_value=int(d2 + 1),
      value=max(10000, d3_min),
      step=100,
      key="d3",
  )
  t3_in = st.sidebar.text_input(
      "Time 3 (H:MM:SS or MM:SS)", value="43:55", key="t3"
  )
else:
  d3, t3_in = None, None

st.sidebar.markdown("---")
pace_unit = st.sidebar.radio(
    "Pace Graph Units:", ["Minutes per KM", "Minutes per Mile"]
)

# --- Main Page Execution ---
t1, t2 = hhmmss_to_seconds(t1_in), hhmmss_to_seconds(t2_in)
t3 = hhmmss_to_seconds(t3_in) if mode == "3 Baseline PBs (More Precise)" else None

valid_inputs = t1 and t2 and (mode == "2 Baseline PBs" or t3)

if valid_inputs:

  # Calculation Engine with 4-Point Synthetic Regression & Log Dampening
  def engine(target_d):
    df_short_raw = t2 / (t1 * (d2 / d1))
    rate_short = math.log(df_short_raw) / math.log(d2 / d1)

    if mode == "2 Baseline PBs":
      decaying_factor = df_short_raw
      denom_ratio = d2 / d1
      if target_d > d2:
        ref_d, ref_t = d2, t2
      else:
        ref_d, ref_t = d1, t1
    else:
      df_long_raw = t3 / (t2 * (d3 / d2))
      rate_long = math.log(df_long_raw) / math.log(d3 / d2)

      if target_d <= d2:
        ref_d, ref_t = d1, t1
        denom_ratio = d2 / d1
      else:
        ref_d, ref_t = d2, t2
        denom_ratio = d3 / d2

      # Proportional Log-Space Midpoints for Real Anchors
      s1, s2, s3 = math.log(d1), math.log(d2), math.log(d3)
      mid_short = (s1 + s2) / 2
      mid_long = (s2 + s3) / 2

      # Constructing 4-Point Synthetic Dataset for Least-Squares Regression
      syn_short_d = max(1000, d1 * 0.75)
      syn_long_d = max(d3 * 1.5, 42195)

      syn_short_rate = rate_short * 0.9  # Mild dampening on short tail
      syn_long_rate = rate_long * 1.05  # Asymptotically controlled long tail

      x_points = [
          math.log(syn_short_d),
          mid_short,
          mid_long,
          math.log(syn_long_d),
      ]
      y_points = [syn_short_rate, rate_short, rate_long, syn_long_rate]

      # Least-Squares Linear Regression (Slope & Intercept calculation)
      n = len(x_points)
      mean_x = sum(x_points) / n
      mean_y = sum(y_points) / n

      num = sum((x_points[i] - mean_x) * (y_points[i] - mean_y) for i in range(n))
      den = sum((x_points[i] - mean_x) ** 2 for i in range(n))

      reg_slope = num / den if den != 0 else 0.0
      reg_intercept = mean_y - reg_slope * mean_x

      # Evaluate Target Distance along the Regression Line
      if target_d <= d2:
        eval_d = math.log(max(target_d, syn_short_d))
      else:
        eval_d = math.log(min(target_d, syn_long_d))

      interpolated_rate = reg_slope * eval_d + reg_intercept

      # Safety bounds on interpolated rate
      interpolated_rate = max(-0.2, min(interpolated_rate, 0.5))

      decaying_factor = math.exp(interpolated_rate * math.log(denom_ratio))
      decaying_factor = max(0.90, min(decaying_factor, 1.35))

    exponent = math.log(target_d / ref_d) / math.log(denom_ratio)
    linear_compensation = (target_d / ref_d) * ref_t
    t_predicted = linear_compensation * math.pow(decaying_factor, exponent)

    return t_predicted, decaying_factor

  pred_seconds, final_decay = engine(target_distance)

  # Target Performance Output
  st.success(
      f"### Predicted Performance for {target_distance:,.0f}m:"
      f" **{seconds_to_hhmmss(pred_seconds)}**"
  )

  # --- Model Architecture Description Box ---
  st.markdown("---")
  if mode == "2 Baseline PBs":
    st.info(
        "### 📌 How the 2-PB Constant Model Works\n"
        "This mode computes a **single, global constant rate of decay** from"
        " your two baseline marks, using dynamic reference anchoring to ensure"
        " maximum accuracy across all distances."
    )
  else:
    st.info(
        "### 📌 How the 4-Point Synthetic Regression Model Works\n"
        "This mode combines your **3 historical anchor points** with two"
        " synthetic boundary tails in proportional log-space. By running a"
        " **Least-Squares Regression** across these points, short-distance PR"
        " volatility is safely absorbed, and long-distance predictions remain"
        " robust and asymptotically stable."
    )

  # --- Performance Pace Curve ---
  st.markdown("---")
  st.subheader("📈 Performance Pace Curve (1,500m to Marathon)")

  test_distances = list(range(1500, 42195 + 1, 250))
  if 42195 not in test_distances:
    test_distances.append(42195)

  plot_rows = []
  for td in test_distances:
    t_sec, _ = engine(td)
    pm = 1000 if pace_unit == "Minutes per KM" else 1609.34
    pace_val = (t_sec / td) * pm / 60
    plot_rows.append({"Distance": td, "Pace": pace_val})

  df_plot = pd.DataFrame(plot_rows)

  fig_pace = go.Figure()
  fig_pace.add_trace(
      go.Scatter(
          x=df_plot["Distance"],
          y=df_plot["Pace"],
          name="Model Pace Curve",
          line=dict(color="#1f77b4", width=3),
      )
  )

  current_pm = 1000 if pace_unit == "Minutes per KM" else 1609.34
  current_pace = (pred_seconds / target_distance) * current_pm / 60
  fig_pace.add_trace(
      go.Scatter(
          x=[target_distance],
          y=[current_pace],
          mode="markers",
          name="Selected Target",
          marker=dict(color="gold", size=14, symbol="circle"),
      )
  )

  fig_pace.update_layout(
      xaxis_title="Distance (Meters)",
      yaxis_title=f"Pace ({pace_unit})",
      hovermode="x unified",
  )
  st.plotly_chart(fig_pace, use_container_width=True)

else:
  st.warning(
      "⚠️ Please fill out all necessary historical PR times in the sidebar to"
      " populate the performance visualizations."
  )