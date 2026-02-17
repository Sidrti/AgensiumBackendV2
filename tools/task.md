Technical Specification: Control Group Holdout Planner
This document serves as the implementation guide for developers building or extending the Multi￾Segment Control Group Holdout Planner.

1. Input Definitions & Default Values
   Global Parameters
   These settings apply to all segments to ensure statistical consistency.
   Parameter Type Default Selected Options / Range
   Holdout (Control) Ratio ($R$) Slider 10% 1% to 50%
   Confidence Level Dropdown 95% 90%, 95%, 99%
   Statistical Power Dropdown 80% 80%, 90%
   Segment-Specific Parameters (Per Segment)
   The app should support up to 10 segments.
   Parameter Type Default Description
   Segment Name Text "Segment 1" User-defined label.
   Daily Traffic ($T$) Number 10,000 Unique visitors per day.
   Baseline ($p_1$) Number 4.5% Current conversion rate.
   Lift ($L$) Number 8% Expected relative improvement.
   Value ($V$) Number $120 Revenue generated per conversion.
2. Calculation Logic (The Math)
   For each segment, the logic follows these steps:
   Step 1: Prep Constants
   • Z-scores for Alpha (Confidence):
   o 90% → 1.645
   o 95% → 1.96
   o 99% → 2.57
   • Z-scores for Beta (Power):
   o 80% → 0.841
   o 90% → 1.28
   Step 2: Define Target Rates
   • Control Rate ($p_1$): Baseline / 100
   • Treatment Rate ($p_2$): p1 _ (1 + (Lift / 100))
   Step 3: Calculate Base Sample Size ($n$)
   This calculates users needed per group as if the split was a standard 50/50: n = ((Z_alpha +
   Z_beta)^2 _ (p1*(1-p1) + p2*(1-p2))) / (p1 - p2)^2
   Step 4: Adjust for Imbalanced Holdout Split
   Since business holdouts are rarely 50/50, we adjust the Total Required Users ($N$) for the
   segment:
   • p = HoldoutRatio / 100
   • q = 1 - p
   • ImbalanceFactor = (1/p + 1/q) / 4
   • Segment Total ($N$): (n _ 2) _ ImbalanceFactor
   Step 5: Segment Outputs
   • Duration (Days): N / Traffic
   • Holdout Users: N _ p
   • Holdout Cost ($): HoldoutUsers _ (p1 _ (Lift/100)) _ Value (The revenue lost by keeping a
   portion of users in the lower-performing Control group).
3. Aggregation (Dashboard Results)
   Once individual segment results are calculated, generate the aggregate Global Results:
4. Total Users Required: Sum of all Segment Total (N) values.
5. Max Duration: The Duration (Days) of the slowest segment (the parallel bottleneck).
6. Total Holdout Cost: Sum of all segment Holdout Cost ($) values.
7. UI/UX & CTA
   • Warning Label: If Holdout Users < n, flag the segment as "Under-powered" or display a
   "Small Control" warning.
   • Free Feature Badge: Ensure the header includes a "Free Feature" badge to differentiate
   from paid agentic services.
   • CTA: Include the following banner at the bottom:
   "Want an agentic app like this without the $50K price tag? Build one starting at $2K. Use it internally,
   publish it on your site, or list it on Agensium to earn revenue." Button: [Build My App]
