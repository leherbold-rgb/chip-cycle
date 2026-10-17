# Findings

What the data say, what survived stress testing, what didn't, and what
would make the model better. Every number here comes from
[`results/results.md`](../results/results.md), [`results/stress.md`](../results/stress.md)
and [`results/backtest.md`](../results/backtest.md); rerun `chipcycle analyze`,
`chipcycle stress` and `chipcycle backtest` to regenerate them.

Data: Korean chip (HS 8542) and memory (HS 854232) exports, January 2013 to
December 2025, so year-over-year growth from 2014. Korea's total exports go
back to 1957. Micron revenue covers 69 quarters from SEC filings.

---

## The short version

1. **Korean memory exports track Micron's revenue almost one-for-one.**
   Correlation 0.93, slope 1.04. Out of sample, they call the direction of
   Micron's revenue growth right in 32 of 35 quarters (91%) and cut the
   error versus a naive guess by 27%. This is the project's strongest and
   most useful result.
2. **Chip exports help call the direction of US industrial production, not
   its size.** Six months ahead, adding memory exports raises correct
   direction calls from 63% to 82%, and the gain survives removing COVID.
   But the size of the forecast gets worse.
3. **Markets move first.** Stock prices peak 2 to 4 months *before* chip
   exports, and past stock moves predict chip exports far better than the
   reverse. By the time the trade data show a boom, prices already know.
4. **The relationship broke in the AI cycle.** The correlation between chip
   exports and US industrial production 3 months later fell from 0.65
   (2014-19) to 0.41 (2020-22) to 0.16 (2023 on), the last one
   indistinguishable from zero.
5. **The headline forecast gain was COVID.** A 10-19% reduction in
   industrial production forecast error looked like the main result. All of
   it came from 2020-21. Without that period, adding chips makes forecasts
   38-66% worse.

---

## 1. What held up

### Micron nowcast

| Version | Quarters | Error, naive | Error, Korea | Direction right | DM p |
|---|---|---|---|---|---|
| Full quarter | 35 | 21.5 pp | 15.6 pp | 91% | 0.05 |
| First 2 months only | 35 | 21.5 pp | 18.0 pp | 91% | 0.13 |
| Before the AI boom (to 2022) | 23 | 19.2 pp | 16.5 pp | 91% | 0.18 |

"pp" is percentage points of year-over-year revenue growth. "DM p" is the
Diebold-Mariano test, which checks whether one forecast is significantly more accurate than another: below 0.05 means the improvement
is unlikely to be luck.

**What it means.** Korea's memory exports and Micron's revenue are two views
of the same market. Korea reports monthly; Micron reports quarterly, three to
four weeks after the quarter ends. Direction accuracy stays at 91% in every
version, which is the robust part. The error reduction is real but only
borderline significant, and weaker with two months of data or before the AI
boom.

**Why it isn't a trading edge by itself.** The comparison is a naive
baseline: "last quarter's growth repeats". Professional investors compare
against Micron's own guidance and analyst consensus, which already absorb
public data like Korea's exports. Beating those is the real test, and it
needs paid data.

### Direction of US industrial production

| Sample | Baseline | With memory exports | Average of the two |
|---|---|---|---|
| All, 6 months ahead | 63% | 82% | 74% |
| Without COVID | 69% | 79% | 75% |
| 2023 on (AI era) | 56% | 67% | 61% |

Chips add 10-20 points of direction accuracy in every sample. The caution:
6-month forecasts made in consecutive months overlap heavily, so 67-83
forecasts are worth roughly a dozen independent calls. Encouraging, not
proven.

---

## 2. What broke under stress testing

### The lead isn't distinguishable from chance

The usual significance cutoff for a correlation with 144 observations is
0.16. That assumes every month is independent. Year-over-year growth rates
share 11 of 12 months with their neighbors, so they aren't. Accounting for
that (phase-randomized surrogates: fake series with the same persistence but no real link):

- the honest cutoff is 0.59-0.70, not 0.16, and
- 144 months of chip data are worth only 10-15 independent observations.

No chip-to-target lead clears it (p = 0.11 to 0.36). Korea's *total* exports,
with 70 years of data, do show a significant link to US industrial
production (p < 0.001), but it is nearly simultaneous, not a lead.

### The forecast gain was COVID

Year by year, almost all of the chip model's advantage comes from 2020 and
2021. COVID crashed industrial production, chip exports turned first, and the
model caught the rebound. In every year since 2023 the chip model was worse.

| Sample | Error change, 3 months | Error change, 6 months |
|---|---|---|
| All | -10% to -11% | -19% |
| Without COVID | +45% to +49% | +38% to +66% |

### It depends on choices more than on the signal

Across 162 reasonable setups (lag lengths, training period, start year, two
growth definitions), chips reduce forecast error less than half the time
and are never statistically significant. A result that flips with setup
choices is not a result.

### Markets

No version predicts stock returns. Out-of-sample R² is negative for every
signal and market, under every assumed release date. In the timing
backtest, the rule "own stocks only while chip export growth is positive"
improved risk-adjusted returns everywhere (global stocks: Sharpe 1.02 vs.
0.65, worst drop 22% vs. 30%). But against 1,000 random strategies with the
same time in the market it landed at the 78th-92nd percentile, never above
the 95th needed to call it skill. The regression-based rule was the worst
performer, consistent with markets leading the data.

---

## 3. Flaws in the model itself

Ordered by how much they matter.

1. **Too little data.** Comtrade's monthly chip data start in 2013. After
   year-over-year growth, that's 144 months, about 10-15 independent
   observations, covering only about two full memory cycles. This is the
   binding constraint; nothing else can fix it.
2. **One regime break dominates.** AI demand separated Korean chip exports
   from the industrial cycle in 2023. A model fitted on 2014-2022 confidently
   predicted a factory boom that didn't happen.
3. **Linear model, unstable relationship.** The model assumes the same
   linear relationship over the whole sample. The stress tests show it
   isn't stable.
4. **Revised data.** US industrial production is revised for months after
   its first release. The model uses today's revised history, which is
   cleaner than what anyone had at the time. Forecast accuracy is therefore
   slightly optimistic.
5. **Approximate release dates.** The registry uses typical publication
   lags, not each month's actual release date.
6. **Value, not volume.** Export values mix price and quantity. Memory prices
   can double in a year, so a "boom" may be pricing, not demand.
7. **Weak baselines for Micron.** Beating "last quarter repeats" is easy.
   Beating guidance and consensus is the bar that matters to investors.
8. **Seasonality.** Korea's data aren't seasonally adjusted. The stress test
   found only mild extra noise from Lunar New Year moving between January
   and February (volatility of growth 30 in those months vs. about 26
   otherwise). Not a major problem.

---

## 4. How to improve it

### Tried here

| Idea | Result |
|---|---|
| Average the baseline and chip forecasts | Removes most of the damage outside the AI era (+0% to +10% error instead of +38% to +66%) and keeps about 75% direction accuracy. Recommended default. |
| Retrain on a rolling 48-month window to adapt to the AI break | Slightly better only in the full sample, which COVID dominates. Without COVID it's 81-117% worse; since 2023, 217-614% worse. Too few observations per fit. Tried once, reported, abandoned. |
| Calculate growth from a smoother 3-month sum | No consistent improvement (part of the 162-setup grid). |

### Worth doing next, in order of expected value

1. **More history.** Korea's trade association (KITA) publishes chip exports
   by Korea's own product codes back to the 1990s. That would roughly double
   the sample and cover the 2001, 2008 and 2011 cycles.
2. **Split price from volume.** Comtrade includes quantities for some codes,
   and DRAMeXchange publishes memory spot prices. Volume should lead the
   real economy; price should lead Micron's margins.
3. **Separate AI demand from the rest.** Use exports by destination: chips
   to Taiwan (where AI accelerators are packaged) vs. to China and Vietnam
   (consumer electronics). The non-AI part may still track the industrial
   cycle.
4. **First-release data.** ALFRED (FRED's archive) holds industrial
   production as originally published. It needs a free API key.
5. **Earlier Korean data.** Korea Customs publishes exports for the first
   20 days of each month around the 21st. For the Micron nowcast, that
   gives three data points per quarter before quarter end.
6. **Predict direction directly.** Since the signal carries direction but
   not size, model the probability that industrial production accelerates
   (a logistic regression) instead of its exact value. Score it with a
   Brier score (the average squared gap between a forecast probability and what happened).
7. **Proper Micron baseline.** Compare against Micron's guidance midpoint,
   which is published in each earnings release, to see whether Korea's data
   add anything beyond what management already says.

---

## 5. How to describe this honestly

> "I tested whether Korean chip exports lead the global cycle. On a
> standard correlation they appear to lead US industrial production by
> several months. But once I accounted for how persistent these series are,
> the lead wasn't distinguishable from chance with 13 years of data. The
> apparent forecasting gain turned out to be entirely the COVID rebound, and
> the relationship broke down in the AI cycle. What did hold up was narrower
> and more useful: Korean memory exports track Micron's revenue almost
> one-for-one and call the direction of its growth right about 90% of the
> time, months before Micron reports."

The negative results are worth leading with. Building a backtest is easy;
showing you can find where your own model is fooling you is the harder
skill, and it's what interviewers in research roles want to hear.
