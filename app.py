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
    "A professional performance model powered by midpoint-derived piecewise rates"
    " and exact PB anchoring."
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

  def raw_engine(target_d):
    df_short_raw = t2 / (t1 * (d2 / d1))
    rate_short = math.log(df_short_raw) / math.log(d2 / d1)

    if mode == "2 Baseline PBs":
      if target_d > d2:
        ref_d, ref_t = d2, t2
        denom_ratio = d2 / d1  # fallback ratio
      else:
        ref_d, ref_t = d1, t1
        denom_ratio = d2 / d1
      decaying_factor = max(1.0, df_short_raw)
    else:
      df_long_raw = t3 / (t2 * (d3 / d2))
      rate_long = math.log(df_long_raw) / math.log(d3 / d2)

      # 1. Local PB Interval Anchoring for Absolute Precision at PRs
      if target_d <= d2:
        ref_d, ref_t = d1, t1
        denom_ratio = d2 / d1
      else:
        ref_d, ref_t = d2, t2
        denom_ratio = d3 / d2

      # 2. Midpoint & Synthetic 4-Point Rate Structure
      s1, s2, s3 = math.log(d1), math.log(d2), math.log(d3)
      x1 = math.log(1500)
      x2 = (s1 + s2) / 2
      x3 = (s2 + s3) / 2
      x4 = math.log(42195)

      y2 = max(0.001, rate_short)
      y3 = max(0.001, rate_long)
      y1 = max(0.001, y2 * 0.9)  # Log-dampened short tail
      y4 = max(0.001, y3 * 1.05)  # Log-dampened marathon tail

      s_target = math.log(target_d)

      # 3. Piecewise Linear Interpolation across the 4 points
      if s_target <= x2:
        dx = x2 - x1
        m = (y2 - y1) / dx if dx != 0 else 0.0
        interpolated_rate = y1 + m * (s_target - x1)
      elif s_target <= x3:
        dx = x3 - x2
        m = (y3 - y2) / dx if dx != 0 else 0.0
        interpolated_rate = y2 + m * (s_target - x2)
      else:
        dx = x4 - x3
        m = (y4 - y3) / dx if dx != 0 else 0.0
        if s_target <= x4:
          interpolated_rate = y3 + m * (s_target - x3)
        else:
          raw_surplus = s_target - x4
          damped_surplus = math.log(1.0 + raw_surplus)
          interpolated_rate = y4 + 0.02 * damped_surplus

      interpolated_rate = max(0.001, min(interpolated_rate, 0.5))
      decaying_factor = math.exp(interpolated_rate * math.log(denom_ratio))
      decaying_factor = max(1.0, min(decaying_factor, 1.35))

    exponent = math.log(target_d / ref_d) / math.log(denom_ratio)
    linear_compensation = (target_d / ref_d) * ref_t
    t_predicted = linear_compensation * math.pow(decaying_factor, exponent)

    return t_predicted, decaying_factor

  # Build unified test distances including target distance
  test_distances = list(range(1500, 42195 + 1, 250))
  if target_distance not in test_distances:
    test_distances.append(target_distance)
  test_distances = sorted(list(set(test_distances)))

  pm_ref = 1000 if pace_unit == "Minutes per KM" else 1609.34
  curve_data = []
  max_pace_so_far = 0.0

  for td in test_distances:
    t_sec, _ = raw_engine(td)
    pace_val = (t_sec / td) * pm_ref / 60
    if pace_val < max_pace_so_far:
      pace_val = max_pace_so_far
      t_sec = (pace_val * 60 / pm_ref) * td
    else:
      max_pace_so_far = pace_val

    curve_data.append({"Distance": td, "Pace": pace_val, "Time": t_sec})

  target_row = next(
      item for item in curve_data if item["Distance"] == target_distance
  )
  pred_seconds = target_row["Time"]

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
        "Computes a consistent rate of decay from your two baselines with"
        " precise local anchoring."
    )
  else:
    st.info(
        "### 📌 How the Midpoint-Rate Piecewise Model Works\n"
        "Rates are calculated at log-space midpoints and extrapolated via"
        " piecewise linear segments with log dampening, while local PB"
        " anchoring guarantees 100% precision at your historical anchor points."
    )

  # --- Performance Pace Curve ---
  st.markdown("---")
  st.subheader("📈 Performance Pace Curve (1,500m to Marathon)")

  df_plot = pd.DataFrame(curve_data)

  fig_pace = go.Figure()
  fig_pace.add_trace(
      go.Scatter(
          x=df_plot["Distance"],
          y=df_plot["Pace"],
          name="Model Pace Curve",
          line=dict(color="#1f77b4", width=3),
      )
  )

  current_pace = target_row["Pace"]
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