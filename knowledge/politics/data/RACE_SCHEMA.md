# Race analog dataset — schema

One row per Senate or governor general election. Files: `races_<cycles>.csv` in this folder, UTF-8,
comma-separated, header row exactly as below, quoted strings where needed. Margins are **D minus R in
percentage points** of the two-party-or-total vote as the source reports (say which in `notes` if unusual).
Unknown = empty cell, never a guess.

| column | type | meaning |
|---|---|---|
| race_id | str | `<year>-<office>-<ST>`, e.g. `2022-senate-PA`; special elections `2022-senate-OK-special` |
| year | int | election year |
| office | str | `senate` or `governor` |
| state | str | 2-letter code |
| cycle_type | str | `midterm` or `presidential` |
| pres_party | str | party of the sitting president on election day: D/R |
| d_candidate, r_candidate | str | major-party nominees |
| incumbent_running | str | D, R, or none (open seat) |
| seat_party_before | str | party holding the seat before the election |
| state_prior_pres_margin | float | D−R margin in the state in the most recent presidential election before this one (for presidential-year races, use the previous cycle, NOT the same-day result) |
| d_prior_statewide | int | 1 if the D nominee previously won a statewide election (incl. Lt Gov, AG, etc.) |
| r_prior_statewide | int | same for R |
| d_well_known | int | 1 if the D nominee had high pre-race name ID (statewide officeholder, national figure, celebrity) |
| r_well_known | int | same for R |
| d_outsider | int | 1 if the D nominee never held elected office (celebrity/businessman/etc.) |
| r_outsider | int | same for R |
| r_trump_endorsed | int | 1 if Trump endorsed the R nominee in the primary or before it |
| d_scandal | int | 1 if a widely-covered personal scandal hit the D nominee during the race |
| r_scandal | int | same for R |
| d_net_fav | float | D nominee net favorability (fav−unfav) in a public poll within ~6 weeks of election |
| r_net_fav | float | same for R |
| fundraising_ratio_d_over_r | float | D candidate total raised ÷ R candidate total raised (FEC/OpenSecrets; governor races: state reports) |
| final_poll_avg_margin | float | final polling average D−R on election eve (RCP, 538 or other named aggregator; prefer 538 then RCP) |
| poll_avg_source | str | which aggregator |
| actual_margin | float | certified D−R margin (empty for 2026) |
| poll_miss | float | actual_margin − final_poll_avg_margin (positive = Democrat outperformed polls; empty for 2026) |
| winner | str | D/R/other (empty for 2026) |
| as_of | date | date the poll average/fav numbers are from (for 2026: the date you collected them) |
| sources | str | semicolon-separated URLs backing the row |
| notes | str | short free text (e.g. "Oz carpetbagger attacks; Fetterman stroke") |
