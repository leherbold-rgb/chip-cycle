# Study guide

This guide assumes you know macro, supply chains and basic finance, but not
statistics or programming. Every technical term is explained the first time
it appears, and there's a glossary at the end.

Suggested order:
1. Part 0 (statistics primer), slowly. Everything else builds on it.
2. Parts 1-2 (the economics and the data).
3. Part 3 (the method), one stage at a time, with the matching section of
   `results/` open beside it.
4. [`FINDINGS.md`](FINDINGS.md) for what the model found and where it fails.
5. Part 5 (how to talk about it) last.

---

## Part 0: Statistics primer

You need about ten ideas. Each is explained with an example from this project.

### Correlation

A number from -1 to +1 measuring how closely two series move together.
+1: always move together. 0: no linear relationship. -1: always opposite.
Rough feel: 0.3 is weak, 0.6 is meaningful, 0.9 is very strong.

*Example:* Korean memory export growth and Micron revenue growth have a
correlation of 0.93. When one is up a lot, so is the other.

Correlation says nothing about which causes which, or whether either is
useful for prediction.

### Lag and lead

Comparing this month's value of one series with a *later* month's value of
another. If chip exports in January correlate best with industrial
production in April, chip exports **lead** by 3 months (equivalently,
production **lags** by 3).

### Growth rates and logs

The project compares growth rates, not levels (see "spurious regression"
below). It uses **log growth**: `100 × (ln(this year) − ln(last year))`. For
small changes this is almost identical to percent change (10% growth ≈ 9.5
log points). Logs are used because they add up neatly over time and treat
rises and falls symmetrically: up 50% and back down is +40.5 then −40.5 log
points, which cancel exactly, whereas in plain percent it's +50% then −33%.

**Year-over-year (YoY)** means comparing with the same month a year earlier.
That also removes seasonal patterns: December always beats January, but
December this year vs. December last year is a fair comparison.

### Regression

Fitting a straight line through data: `y = a + b × x`. **b** (the slope, or
"beta") says how much y moves when x moves by 1. With several x variables,
each gets its own slope. All forecasting models in this project are
regressions.

*Example:* the Micron model's slope is 1.04. When Korean memory export growth
is 10 points higher, Micron's revenue growth tends to be about 10.4 points
higher.

### p-value

The probability of seeing a result at least this strong **if there were
really nothing there**, purely by luck. Convention: below 0.05 (5%) counts as
"statistically significant".

*Example:* the Micron nowcast improvement has p = 0.05. If Korean exports
were useless, an improvement this big would happen by luck about 5% of the
time. Borderline.

Two traps:
- **p = 0.05 isn't 95% certainty that the effect is real.** It only says the
  result would be unusual if there were no effect.
- **Test 20 things and one will pass by luck.** This is the *multiple
  testing* problem; see Part 3, stress tests.

### Autocorrelation (persistence)

How much a series resembles its own recent past. YoY growth rates are
extremely persistent: this month's YoY shares 11 of its 12 months with last
month's, so the two are nearly identical.

This matters because statistics usually assume each observation is new
information. When they aren't, you have fewer real observations than rows,
results look more significant than they are, and two persistent series can
correlate strongly by coincidence. This is the most important technical
point in the project, and the stress tests are mostly about it.

### Stationarity

A series is **stationary** if its average and its typical swing size don't
drift over time. Growth rates usually are; levels (GDP, stock prices) usually
aren't, since they trend up. Most statistical tools assume stationarity.

### Spurious regression

Two trending series will correlate even with no connection. Korea's exports
and the number of Netflix subscribers both rose from 2013 to 2025, so their
levels correlate. Their growth rates don't. Hence: always use growth rates.

### In-sample vs. out-of-sample

**In-sample:** you fit the model on all the data and measure how well it fits
that same data. This is always flattering, because the model has seen the
answers.

**Out-of-sample:** you fit using only data up to some date, predict the
future, and score it once the future arrives. This is what someone using the
model in real time would actually experience. Only out-of-sample results
count as evidence of usefulness.

### Overfitting and data snooping

**Overfitting:** a model complex enough to fit noise. It looks great on past
data and fails on new data.

**Data snooping:** trying many variations and reporting the one that
worked. Even if each variation is honest, picking the best is not. That's why
the backtest rules were fixed before running, and why every result is
reported.

---

## Part 1: The economics

### The claim being tested

Chips sit at the start of almost every supply chain. A carmaker, phone maker
or server builder orders chips months before the finished product ships. So
when companies expect demand to change, chip orders change first, and the
rest of the economy follows. This is the **bullwhip effect** you know from
supply chains, viewed from the upstream end.

Korea is the world's largest memory chip exporter and publishes trade data
unusually fast. If the claim is right, Korean chip exports should move
before factory output, credit conditions and stock prices elsewhere.

### Why memory specifically

Memory chips (DRAM is working memory, NAND is storage) are close to
commodities: one maker's DRAM can replace another's. Their prices swing
hard with supply and demand, so they are a sensitive gauge of the cycle.
Three firms make nearly all DRAM: Samsung and SK Hynix (Korean) and Micron
(US). Korea's memory exports are therefore a monthly read on Micron's
market.

### Two kinds of "lead"

1. **Economic lead.** Chip activity really turns before the rest of the
   economy, because orders come before production.
2. **Publication lead.** Korea simply publishes faster than the US. Both
   numbers can describe the same month, but the Korean one is available
   weeks earlier.

The project separates them: the reference panel tests (1), and release dates
handle (2).

### The AI break

From 2023, Korea's chip exports boomed on demand for high-bandwidth memory
(HBM), the stacked DRAM inside AI accelerators, while factory activity in the
rest of the world stayed flat. A signal that used to track the broad
industrial cycle started tracking AI data-center spending instead. The
results confirm this break clearly (Part 3, Stage 4).

---

## Part 2: The data (Stage 1)

| Series | What it is | Source |
|---|---|---|
| Korea chip exports | Integrated circuits, HS code 8542, monthly USD | UN Comtrade, 2013 on |
| Korea memory exports | DRAM and NAND, HS code 854232 | UN Comtrade, 2013 on |
| Korea total exports | All goods | FRED, 1957 on (long-history check) |
| US industrial production | Output of US factories, mines and utilities | FRED `INDPRO` |
| Baa credit spread | Yield on medium-grade corporate bonds minus the 10-year Treasury yield | FRED `BAA10Y` |
| Net Fed liquidity | Fed balance sheet minus Treasury cash (TGA) minus reverse repo | FRED, combined in Stage 2 |
| ACWI, SOX, MU | Global stocks, chip stocks, Micron shares | Yahoo Finance |
| Micron revenue | Quarterly, from 10-Q and 10-K filings | SEC EDGAR |

**HS codes** are the international product codes customs agencies use. 8542
is "electronic integrated circuits"; 854232 is the memory subset.

**UN Comtrade** is the UN's database of every country's customs data. Korea
reports to it, which gives free, consistent history. It posts data with a
delay of several months, so its most recent month is December 2025.

**FRED** is the St. Louis Fed's free economic database. **SEC EDGAR** is the
database of every US public company filing. **XBRL** is the tagged format
filings use, which lets code read "Revenue" directly.

**Why the Baa spread rather than high yield?** FRED now serves only three
years of the high-yield spread because of licensing. Baa is investment grade,
so it moves less, but it goes back decades.

**Net Fed liquidity:** the Fed's balance sheet adds money to the financial
system. Cash the Treasury keeps at the Fed (the Treasury General Account, or
TGA) and money that money-market funds park at the Fed overnight (the
reverse repo facility, or RRP) take it back out. What's left is a common
proxy for liquidity in markets.

### Release dates and look-ahead bias

Every number has two dates: the period it describes and the day it was
published. US industrial production for March comes out around April 16.

**Look-ahead bias** means using a number before it was published. It is the
most common reason backtests look better than reality. The project stores
both dates and builds two tables:

- the **reference panel**, where values sit under the month they describe,
  for studying the economy, and
- the **real-time panel**, where each row holds only what had been published
  by that date, for testing forecasts and trading rules.

The as-of logic: for each decision date, take the most recent value whose
release date is on or before that date. Tests in `tests/test_timing.py` and
`tests/test_forecast.py` fail if a future value leaks in. One of them
scrambles all data after a cutoff and checks that earlier forecasts don't
change.

**A real bug, worth mentioning in interviews.** An early version of the
forecasting code leaked future data. In Python, `data[0:-5]` means
"everything except the last 5 rows", not "nothing". For the first few
forecasts, a training range that should have been empty silently became
almost the whole dataset, future included. A sanity check caught it: some
6-month forecasts were dated 1958, which was impossible given a 4-year
training minimum. It's fixed, with a test that would catch it again.

---

## Part 3: The method, stage by stage

Each stage below says what it does, why, and how to read its output.

### Stage 2: Transforms and stationarity (`transforms.py`)

**What:** converts every series to 12-month log growth (credit spreads, already
in percent, become 12-month changes), and tests whether each is stationary.

**The tests:**
- **ADF** (Augmented Dickey-Fuller) starts from "this series wanders with no
  anchor" (has a *unit root*). A small p-value rejects that. Good.
- **KPSS** starts from the opposite, "this series is stable". A small p-value
  rejects that. Bad.

**Reading the result:** most targets pass both. Korean chip growth fails ADF
(p around 0.2), not because it wanders but because 144 months is too short
for the test to be sure. Short samples give weak tests. This is the first
sign of the project's biggest limitation.

### Stage 3: Lead-lag (`leadlag.py`)

**Cross-correlation:** correlation of chip exports this month with the target
k months later, for k from −12 to +12. A peak at +3 means chips lead by 3
months; a peak at a negative k means the target moves first.

**Prewhitening:** persistent series correlate at almost every lag, so the raw
cross-correlation looks broad and impressive. Prewhitening strips out the
part of each series that is predictable from its own past, leaving only the
surprises. It uses a filter fitted to the chip series (an *autoregressive
model*, which is a regression of a series on its own past values) and
applies it to both series. If a correlation survives that, it's more
believable.

**Granger causality:** fit a small model predicting the target from its own
past. Then add the chip series' past and test whether predictions improve
(an F-test, which is a standard test for whether extra variables help a
regression). If they do, chips "Granger-cause" the target. This means
*predictive information*, not real causation: a third factor could drive
both, with chips simply reacting faster. The model used is a **VAR (vector
autoregression)**, where each series is predicted from the past of all
series.

**What it found:**
- Raw correlations make chips look like they lead US industrial production
  by about 8 months.
- For stock markets, the raw peak is at −2 to −4 months: **stocks move
  first**. Granger tests agree: stocks predict chip exports (p ≤ 0.006);
  chips mostly don't predict stocks.

### Stage 4: Stability (`stability.py`)

**What:** checks whether the relationship holds across different periods.

- **Regimes:** correlation between chips and industrial production 3 months
  later, separately for 2014-19, 2020-22 and 2023 on, each with a **95%
  confidence interval**. That's the range the true value plausibly lies in;
  if it includes zero, the relationship may not exist in that period.
- **Rolling window:** re-run the cross-correlation in a moving 5-year window
  and track where it peaks.

**What it found:** 0.65 → 0.41 → 0.16. The 2023-on interval runs from −0.18
to +0.46, so it includes zero. The AI break shows clearly.

### Stage 5: Out-of-sample forecasting (`forecast.py`)

**Walk-forward test:** step through history one month at a time. Each month,
fit using only data available up to then, forecast h months ahead (h = 1, 3,
6), and record the error when the actual number arrives. The training
period grows as you go (an **expanding window**).

**Two models compared:**
- **Baseline:** predicts industrial production from its own last 3 months.
- **Augmented:** the same, plus chip exports' last 3 months.

Lag counts were fixed in advance; choosing them by looking at results would
be data snooping.

**Scoring:**
- **RMSE** (root mean squared error): the typical size of a miss. Square each
  error (so misses in either direction count and big misses count more),
  average, take the square root. `rmse_change_pct` of −10 means chips cut
  the typical miss by 10%.
- **Diebold-Mariano (DM) test:** is one model's lower error bigger than luck?
  It compares the two models' squared errors month by month. Forecasts made
  in consecutive months for 3 or 6 months ahead overlap, so their errors are
  related; the test adjusts for that (with what's called a *Newey-West*
  correction) and for small samples.

**Markets:** on the 16th of each month (after Korea's customs data are out),
predict the next 3 months' stock return from the latest chip growth figure.
- The baseline is the **historical average return**. In finance, beating "it
  will return its average" is famously hard.
- **Out-of-sample R²** is the share of the baseline's squared error the model
  removes. Above 0 means it beat the average. For monthly stock returns,
  even +1% is meaningful. Negative means it did worse than simply guessing
  the average.

**What it found:** chips cut 3- and 6-month industrial production errors by
10-19%, but not significantly (DM p ≈ 0.14-0.18). Market R² was negative
everywhere. The stress tests then showed the 10-19% was all COVID.

### Stage 6: Micron (`micron.py`)

**Fiscal quarters:** Micron's year ends around early September, so its
quarters run roughly Sep-Nov, Dec-Feb, Mar-May and Jun-Aug. The code reads
each quarter's exact dates from Micron's SEC filings and adds up Korea's
memory exports over the matching months. Micron doesn't report its fourth
quarter on its own, so Q4 is calculated as the annual total minus Q1-Q3.

**Nowcast:** estimating a number for a period that has already happened
but hasn't been reported yet. Here: predict this quarter's Micron revenue
growth from Korea's memory export growth over the same months, using a
regression fitted only on earlier quarters. The baseline is "last quarter's
growth repeats".

**What it found:** correlation 0.93, direction right in 91% of quarters,
error 27% lower than the baseline. See FINDINGS for how it held up.

### Stress tests (`robustness.py`, `chipcycle stress`)

Each test tries to break a result from the stages above.

**Surrogate test.** The standard significance cutoff assumes independent
observations, which persistent growth rates aren't. Also, picking the best
of 12 lags gives 12 chances to get lucky. The fix: create 500 fake versions
of the chip series that have exactly the same persistence and volatility but
no real link to anything. (Technically: *phase-randomized surrogates*. They
keep the series' frequency content, so they have the same rhythm, but
scramble its timing.) Run the same "best lead" search on each fake. If the
real result doesn't beat 95% of the fakes, it isn't distinguishable from
chance. Result: the honest cutoff was about 0.6 instead of the textbook
0.16, and no chip lead passed.

**Effective sample size.** How many independent observations the data are
really worth after accounting for persistence. 144 months of YoY growth ≈
10-15 independent observations.

**Multiple testing (Benjamini-Hochberg).** With 18 pairs tested, some will
pass by luck. The Benjamini-Hochberg method adjusts each p-value upward to
control the share of false discoveries among the "significant" results.

**Specification grid.** Re-run the forecasting test under 162 different
reasonable setups (lag counts, training length, start year, growth
definition) and see how often the result holds. A real effect shows up in
most of them; a fragile one flips around. Result: chips helped in under half
and were never significant.

**COVID check.** Recompute the forecast results year by year, and without
March 2020 to June 2021. Result: the whole gain came from those months.

**Bootstrap interval.** Resample the forecast errors in 6-month blocks
thousands of times to see how much the out-of-sample R² could vary by
chance. Blocks keep the month-to-month structure intact. The intervals for
market R² all include zero or below.

**Forecast combination.** Average the baseline and chip forecasts. It's
well established in forecasting that simple averages often beat either model
alone, because the errors partly cancel. It worked here outside the AI era.

### Backtest (`backtest.py`, `chipcycle backtest`)

**Direction accuracy:** how often the model correctly calls whether
industrial production growth will be higher or lower in h months than
today. A coin flip gets 50%.

**Trading rules,** fixed before running:
- *level:* own the index while chip export growth is above zero, else cash
- *momentum:* own it while chip export growth is higher than 3 months ago
  (the cycle is improving)
- *model:* own it while the Stage 5 regression predicts above-average returns

Rebalanced monthly on the 16th, 10 basis points of cost per switch (a
**basis point** is 0.01%), cash earns zero.

**Performance measures:**
- **CAGR** (compound annual growth rate): the average yearly return,
  compounded.
- **Volatility:** how much returns swing, annualized standard deviation.
- **Sharpe ratio:** return divided by volatility, i.e. return per unit of
  risk. Around 0.5 is typical for stocks; above 1 is very good.
- **Max drawdown:** the worst peak-to-bottom fall along the way.
- **Random-timing percentile:** compare the rule against 1,000 random
  strategies that hold the market for the same share of months. A rule
  invested 70% of the time looks good in a rising market by default; this
  checks whether the *timing* added anything. Above 95 suggests real skill;
  around 50 means none.

**What it found:** the *level* rule reduced risk on every market but landed
at the 78th-92nd percentile, short of the 95 needed. The *model* rule was
worst, consistent with markets moving before the data.

---

## Part 4: Running it yourself

You need Python 3.11+. In a terminal, inside the project folder:

```bash
python -m venv .venv            # create an isolated Python environment
source .venv/bin/activate       # switch into it (Windows: .venv\Scripts\activate)
pip install -e ".[dev]"         # install the project and its libraries
pytest                          # run the tests (should all pass)
chipcycle fetch                 # download data (Comtrade takes ~45 minutes, rate limited)
chipcycle analyze               # stages 2-6 → results/results.md
chipcycle stress                # stress tests → results/stress.md (~15 minutes)
chipcycle backtest              # backtest → results/backtest.md
```

**Map of the code** (`src/chipcycle/`):

| File | Job |
|---|---|
| `registry.py` | List of every series: source, code, frequency, release lag |
| `ingest/` | One downloader per source (FRED, Yahoo, Comtrade, manual CSV) |
| `cache.py` | Saves downloads to `data/raw/` so analysis doesn't need the network |
| `timing.py` | Monthly alignment; reference and real-time panels |
| `transforms.py` | Growth rates, liquidity, stationarity tests (Stage 2) |
| `leadlag.py` | Cross-correlation, prewhitening, Granger tests (Stage 3) |
| `stability.py` | Regimes and rolling windows (Stage 4) |
| `forecast.py` | Walk-forward forecasts, Diebold-Mariano, market test (Stage 5) |
| `micron.py` | SEC revenue, quarter mapping, nowcast (Stage 6) |
| `robustness.py` | Stress tests |
| `backtest.py` | Direction accuracy and trading rules |
| `report.py` | Runs everything and writes `results/` |
| `cli.py` | The `chipcycle` commands |

The libraries used: **pandas** (tables of data), **numpy** (math on arrays),
**statsmodels** (statistical tests and models), **scipy** (probability
distributions), **matplotlib** (charts), **requests** and **yfinance**
(downloading), **pytest** (tests).

---

## Part 5: How to talk about it

### 30 seconds

> "I tested whether Korean chip exports lead the global economy. Korea
> publishes trade data within weeks, before almost any other hard data. I
> built a pipeline that lines it up with US industrial production, credit
> spreads, Fed liquidity and stock prices using publication dates, so
> there's no look-ahead bias, then tested it out of sample and stress-tested
> it. The headline lead turned out to be fragile: once I accounted for how
> persistent these series are, it wasn't distinguishable from chance, the
> forecasting gain was entirely the COVID rebound, and the relationship
> broke in the AI cycle. What held up was narrower: Korean memory exports
> track Micron's revenue almost one-for-one and called the direction of its
> growth right in 32 of 35 quarters, before Micron reports."

### Resume bullets (real numbers)

- Built a Python pipeline aligning Korean semiconductor trade data (UN
  Comtrade), US macro series (FRED), equities and SEC filings by
  publication date to test whether chip exports lead the global cycle;
  31 unit tests guard against look-ahead bias.
- Showed an apparent 10-19% forecast-error reduction for US industrial
  production came entirely from the COVID rebound, using surrogate
  significance tests, a 162-specification robustness grid and
  Diebold-Mariano tests; documented the relationship's breakdown in the
  2023+ AI cycle (correlation 0.65 → 0.16).
- Developed a Micron revenue nowcast from Korean memory exports
  (correlation 0.93) that called revenue growth direction correctly in 91%
  of 35 out-of-sample quarters and cut error 27% versus a naive baseline.

### Questions you should be able to answer

**Why growth rates instead of levels?** Trending levels correlate
spuriously. Year-over-year growth removes trends and seasonality.

**What's prewhitening?** Removing each series' predictable part before
correlating, so you compare surprises. Persistent series otherwise
correlate at every lag.

**Is Granger causality real causation?** No. It's predictive information. A
common driver, like demand expectations, could move both.

**How did you avoid look-ahead bias?** Release lags for every series, a
backward as-of join on release dates, expanding-window forecasts, and tests
that fail if future data leak in. I found and fixed one leak myself.

**Your lead looked significant at first. What changed?** The standard
significance band assumes independent data. Year-over-year growth rates
overlap 11 of 12 months, so 144 months were worth about 10-15 independent
observations. Using surrogates that keep that persistence, the honest cutoff
was about 0.6, not 0.16, and nothing passed.

**Why didn't it predict stocks?** Markets move first. Prices discount
expected demand before it shows up in trade data. Granger tests ran from
stocks to chip exports, not the other way.

**Then is the project useless?** No. It answered the question, and the
answer for markets and the broad economy is "not reliably, with this
data". It found one useful, robust relationship (Micron) and showed exactly
why the popular story (chips lead the economy) is weaker than it looks. That
is what research is for.

**What's the weakest part?** Sample size: chip data from 2013 only, about
two memory cycles. Second: the AI regime break. Third: revised rather than
first-release data.

**What would you do next?** Longer history from KITA; split price from
volume; separate AI-related exports by destination; first-release data from
ALFRED; compare the Micron nowcast against Micron's own guidance.

---

## Glossary

| Term | Meaning |
|---|---|
| Autocorrelation | How much a series resembles its own past; high means persistent |
| Autoregressive (AR) model | A regression of a series on its own past values |
| Backtest | Testing a rule or model on historical data as if in real time |
| Basis point | 0.01%. 10 bp = 0.1% |
| Benjamini-Hochberg | Adjustment of p-values for testing many things at once |
| Beta (slope) | How much y moves when x moves by 1 in a regression |
| Bootstrap | Resampling the data many times to see how much a result could vary |
| CAGR | Compound annual growth rate |
| Confidence interval | The range the true value plausibly lies in (95% CI: 95% of the time) |
| Correlation | -1 to +1 measure of how closely two series move together |
| Cross-correlation | Correlation between one series and a shifted version of another |
| Data snooping | Trying many variations and reporting the best |
| Diebold-Mariano test | Tests whether one forecast is significantly more accurate than another |
| Direct forecast | A separate model for each forecast horizon |
| Drawdown | Fall from a previous peak; max drawdown is the worst one |
| Effective sample size | Number of independent observations the data are really worth |
| Expanding window | Each refit uses all data up to that point |
| F-test | Test of whether added variables improve a regression |
| Forecast combination | Averaging forecasts from several models |
| Granger causality | Past x improves the forecast of y beyond y's own past |
| HS code | International customs product code |
| HBM | High-bandwidth memory, stacked DRAM used in AI chips |
| In-sample | Measured on the same data the model was fitted to |
| Look-ahead bias | Using information before it was available |
| Log growth | 100 × difference in natural logs; ≈ percent change |
| Nowcast | Estimating a number for a period that has happened but isn't reported yet |
| Out-of-sample | Measured on data the model hadn't seen when fitted |
| OOS R² | Share of the baseline's squared error the model removes, out of sample |
| Overfitting | A model that fits noise; good on old data, bad on new |
| p-value | Chance of a result this strong if there were really no effect |
| Phase-randomized surrogate | Fake series with the same rhythm and persistence, but no link to anything |
| Prewhitening | Removing a series' predictable part before correlating |
| Regime | A period with its own stable behavior (e.g., the AI cycle) |
| Regression | Fitting a line (or plane) through data |
| RMSE | Root mean squared error, the typical size of a forecast miss |
| Rolling window | Each refit uses only the most recent N periods |
| Sharpe ratio | Return divided by volatility |
| Spurious regression | Strong correlation between unrelated trending series |
| Stationary | Average and swing size don't drift over time |
| Unit root | A series that wanders with no anchor |
| VAR | Vector autoregression: each series predicted from the past of all series |
| Volatility | Annualized standard deviation of returns |
| YoY | Year over year, compared with the same period a year earlier |
