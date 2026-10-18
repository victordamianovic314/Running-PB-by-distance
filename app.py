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
    "A professional performance model powered by exact flat-capped rate"
    " interpolation and recursive mesh anchoring."
)
st.markdown("---")

# --- Sidebar Inputs ---
st.sidebar.header("⚙️ Configuration")
mode = st.sidebar.radio(
    "Calculator Precision Mode:",
    ["2 Baseline PBs", "3 Baseline PBs (More Precise)"],
    index=0,
)

st.sidebar.markdown("---")
st.sidebar.header("🎯 Target Distance")
target_distance = st.sidebar.number_input(
    "Desired Target Distance (meters)",
    min_value=1500,
    max_value=42195,
    value=10000,
    step=100,
)

st.sidebar.markdown("---")
st.sidebar.header("📋 Baseline Performances")

st.sidebar.subheader("Baseline 1 (Short)")
d1 = st.sidebar.number_input(
    "Distance 1 (meters)", min_value=100, value=3000, step=100, key="d1"
)
t1_in = st.sidebar.text_input("Time 1 (H:MM:SS or MM:SS)", value="7:24", key="t1")

st.sidebar.subheader("Baseline 2 (Mid)")
d2 = st.sidebar.number_input(
    "Distance 2 (meters)", min_value=int(d1 + 1), value=5000, step=100, key="d2"
)
t2_in = st.sidebar.text_input(
    "Time 2 (H:MM:SS or MM:SS)", value="12:37", key="t2"
)

if mode == "3 Baseline PBs (More Precise)":
  st.sidebar.subheader("Baseline 3 (Long)")
  d3 = st.sidebar.number_input(
      "Distance 3 (meters)", min_value=int(d2 + 1), value=42195, step=100, key="d3"
  )
  t3_in = st.sidebar.text_input(
      "Time 3 (H:MM:SS or MM:SS)", value="2:01:41", key="t3"
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

  # --- Rate Calculations ---
  df_short_raw = t2 / (t1 * (d2 / d1))
  rate_short = max(0.001, math.log(df_short_raw) / math.log(d2 / d1))

  if mode == "2 Baseline PBs":
    base_mesh = [(d1, t1), (d2, t2)]
    rate_long = rate_short
  else:
    df_long_raw = t3 / (t2 * (d3 / d2))
    rate_long = max(0.001, math.log(df_long_raw) / math.log(d3 / d2))
    base_mesh = [(d1, t1), (d2, t2), (d3, t3)]

    s1, s2, s3 = math.log(d1), math.log(d2), math.log(d3)
    x2, x3 = (s1 + s2) / 2, (s2 + s3) / 2

    def get_interpolated_rate(d_target):
      s_target = math.log(d_target)
      if s_target < x2:
        return rate_short
      elif s_target <= x3:
        dx = x3 - x2
        m = (rate_long - rate_short) / dx if dx != 0 else 0.0
        return rate_short + m * (s_target - x2)
      else:
        return rate_long

    def compute_projected_time(d_from, t_from, d_target, rate_val, forward=True):
      denom_ratio = (d2 / d1) if (forward and d_target <= d2) else (d3 / d2)
      exponent = math.log(d_target / d_from) / math.log(max(1.001, denom_ratio))
      decaying_factor = math.exp(rate_val * math.log(max(1.001, denom_ratio)))
      if forward:
        return (d_target / d_from) * t_from * math.pow(decaying_factor, exponent)
      else:
        return (
            (d_target / d_from)
            * t_from
            / math.pow(decaying_factor, abs(exponent))
        )

    def recursive_subdivide(d_a, t_a, d_b, t_b, rate_s, rate_l):
      if (d_b - d_a) < 100:
        return []
      d_mid = math.sqrt(d_a * d_b)
      rate_mid = get_interpolated_rate(d_mid)
      t_fwd = compute_projected_time(d_a, t_a, d_mid, rate_mid, forward=True)
      t_bwd = compute_projected_time(d_b, t_b, d_mid, rate_mid, forward=False)
      t_mid = (t_fwd + t_bwd) / 2.0

      left_sub = recursive_subdivide(d_a, t_a, d_mid, t_mid, rate_s, rate_l)
      right_sub = recursive_subdivide(d_mid, t_mid, d_b, t_b, rate_s, rate_l)
      return left_sub + [(d_mid, t_mid)] + right_sub

    dense_mesh = []
    for i in range(len(base_mesh) - 1):
      d_a, t_a = base_mesh[i]
      d_b, t_b = base_mesh[i + 1]
      dense_mesh.append((d_a, t_a))
      sub_points = recursive_subdivide(
          d_a, t_a, d_b, t_b, rate_short, rate_long
      )
      dense_mesh.extend(sub_points)
    dense_mesh.append(base_mesh[-1])
    dense_mesh = sorted(list(set(dense_mesh)), key=lambda x: x[0])

  # --- Evaluation Engine ---
  def evaluate_target(target_d):
    if mode == "2 Baseline PBs":
      ref_d, ref_t = d2, t2
      denom_ratio = d2 / d1
      decaying_factor = math.exp(rate_short * math.log(denom_ratio))
      decaying_factor = max(1.0, decaying_factor)
      exponent = math.log(target_d / ref_d) / math.log(denom_ratio)
      linear_compensation = (target_d / ref_d) * ref_t
      return linear_compensation * math.pow(decaying_factor, exponent)
    else:
      min_d, min_t = base_mesh[0]
      max_d, max_t = base_mesh[-1]

      if target_d < min_d:
        denom_ratio = d2 / d1
        decaying_factor = math.exp(rate_short * math.log(denom_ratio))
        exponent = math.log(target_d / min_d) / math.log(denom_ratio)
        linear_compensation = (target_d / min_d) * min_t
        return linear_compensation * math.pow(decaying_factor, exponent)

      if target_d > max_d:
        denom_ratio = d3 / d2
        decaying_factor = math.exp(rate_long * math.log(denom_ratio))
        exponent = math.log(target_d / max_d) / math.log(denom_ratio)
        linear_compensation = (target_d / max_d) * max_t
        return linear_compensation * math.pow(decaying_factor, exponent)

      for i in range(len(dense_mesh) - 1):
        d_a, t_a = dense_mesh[i]
        d_b, t_b = dense_mesh[i + 1]
        if d_a <= target_d <= d_b:
          fraction = (target_d - d_a) / (d_b - d_a) if d_b != d_a else 0.0
          return t_a + fraction * (t_b - t_a)
      return max_t

  # Build curve data for plot using 200m checkpoints evaluated through the model
  max_plot_d = (
      max(d2, target_distance)
      if mode == "2 Baseline PBs"
      else max(42195, d3, target_distance)
  )
  test_distances = list(range(int(d1), int(max_plot_d) + 1, 200))
  if target_distance not in test_distances:
    test_distances.append(target_distance)
  test_distances = sorted(list(set(test_distances)))

  pm_ref = 1000 if pace_unit == "Minutes per KM" else 1609.34
  curve_data = []

  for td in test_distances:
    t_sec = evaluate_target(td)
    pace_val = (t_sec / td) * pm_ref / 60
    curve_data.append({"Distance": td, "Pace": pace_val, "Time": t_sec})

  pred_seconds = evaluate_target(target_distance)

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
        "Computes a consistent fixed decay rate from your two baselines using"
        " logarithmic ratio scaling.\n\n"
        "**Core Formula:**\n"
        "$$T_{\\text{predicted}} = \\left(\\frac{D}{D_{\\text{ref}}}\\right)"
        " T_{\\text{ref}} \\cdot \\left(\\text{decaying\_factor}\\right)^{\\frac{\\ln(D"
        " / D_{\\text{ref}})}{\\ln(D_2 / D_1)}}$$"
    )
  else:
    st.info(
        "### 📌 How the Plateau-Capped Recursive Model Works\n"
        "Rates are derived via exact linear interpolation and flat outer caps,"
        " while times across intervals are solved using recursive bidirectional"
        " mesh averaging down to sub-100m steps."
    )

  # --- Performance Pace Curve ---
  st.markdown("---")
  st.subheader("📈 Performance Pace Curve")

  df_plot = pd.DataFrame(curve_data)

  fig_pace = go.Figure()
  fig_pace.add_trace(
      go.Scatter(
          x=df_plot["Distance"],
          y=df_plot["Pace"],
          name="Pace Curve",
          line=dict(color="#1f77b4", width=3),
      )
  )

  current_pace = (pred_seconds / target_distance) * pm_ref / 60
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