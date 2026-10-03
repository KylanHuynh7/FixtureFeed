# Data-source spike: NFL schedules (2026-10-03)

Approved as DECISIONS.md #11. Read-only, nothing installed, nothing committed. This report lists options; it does not pick one.

## Requests made

| Source | Data requests | Doc/terms reads | Samples saved (`research/spike/samples/`) |
|---|---|---|---|
| nflverse (GitHub) | 1 (`games.csv`) | 4 (DATASETS.md, LICENSE [404], commit history API, repo metadata API) | `nflverse_games.csv` |
| ESPN site API | 3 | 1 (Disney terms) | none (deleted 2026-10-03 at director's request) |
| TheSportsDB | 1 | 2 (docs, terms) | `tsdb_nfl_season_2026.json` |
| API-Sports | 0 | 1 search; site returned 403 to page fetches | none |
| MySportsFeeds | 0 | 1 (pricing page) | none |
| NFL.com | 0 | 1 (terms) | none |
| Pro-Football-Reference | 0 | 1 (bot policy) | none |

**Process issue:** I made the 3 ESPN data requests *before* reading ESPN's terms. Those terms (below) prohibit automated access. The samples were never committed and were deleted on 2026-10-03 at your request.

## Source findings

### 1. nflverse `games.csv` (github.com/nflverse/nfldata)
- **Availability / auth:** public file on GitHub, no key needed. Returned HTTP 200, 2.2 MB, 272 games for the 2026 season.
- **Freshness:** a bot ("Automated data update") committed to it 5+ times on 2026-10-03, about every 10–120 minutes. Good freshness.
- **Game ID:** `2026_04_PIT_CLE` = season_week_away_home. **Not stable if a game changes weeks.** Evidence: the 2020 DEN@NE game was originally scheduled for week 5 and moved to week 6. Its ID is now `2020_06_DEN_NE`, so the old week-5 ID no longer exists. The file also has `old_game_id` (date-based, which also changes), `gsis`, `pfr` and `espn` IDs.
- **TBD times:** not marked. All week 18 games show `13:00`, a placeholder the NFL hasn't announced yet. A feed would show a confident wrong time.
- **Time zone:** `gametime` is documented as US Eastern, no offset. We'd have to convert, including around the DST change.
- **Cancellations:** the cancelled 2022 BUF@CIN game (week 17) is **missing from the file entirely**. A game disappearing would have to be read as "cancelled or removed", not ignored.
- **Terms:** **no license** (no LICENSE file, and GitHub reports `license: null`). Being publicly downloadable is not the same as having explicit permission to reuse. This is low risk for a student project, but it is unclear. The data itself ultimately comes from the NFL.

### 2. ESPN site API (`site.api.espn.com/apis/site/v2/sports/football/nfl/...`)
- **Availability / auth:** no key needed; all 3 requests returned HTTP 200. **Undocumented and unofficial.** It can change or disappear without notice.
- **Game ID:** numeric event ID (e.g. `401873184`). The cancelled 2022 game kept its ID (`401437947`). nflverse records a single ESPN ID for the moved 2020 game, which suggests ESPN IDs survive reschedules, but **I did not directly observe an ID before and after a move.**
- **TBD times:** explicit. `timeValid: false`, with status detail `"1/10 - TBD"`. The placeholder date `2027-01-10T05:00Z` must not be shown as a real time.
- **Time zone:** ISO timestamps in UTC. Easy to handle.
- **Cancellations / postponements:** explicit `STATUS_CANCELED`; the event stays in the data.
- **Terms: prohibitive.** ESPN uses Disney's terms, which forbid accessing content "using a robot, spider, script, or other automated means", "compiling... any collection of data, data set or database", and "any commercial or business-related use". Building FixtureFeed on this would break the spike limit "no scraping... against stated terms", and the risk grows if the project is deployed publicly.

### 3. TheSportsDB (free key `123`)
- **Availability:** HTTP 200, but the free tier caps season events at **15 results**. The response contained only 15 preseason games (Aug 7–15). **The free tier cannot provide a full NFL schedule.**
- **Fields:** stable `idEvent`, `strTimestamp`, `strStatus`, `strPostponed`. Good structure.
- **Terms:** permissive for development ("You can scrape, copy and modify content returned from the API"), with attribution and a link-back required. Commercial or app-store use needs a paid plan.
- **Cost to be usable:** paid plan, which is excluded by the $0 budget.

### 4. API-Sports (API-American-Football): not verified
- Third-party summaries report a free plan of 100 requests per day with signup and no card, covering NFL games. The vendor site returned 403 to my page reads, so I **could not verify** which seasons the free plan covers. I recall that its sister soccer API limits free plans to older seasons, but that is unverified for NFL. Using it requires creating an account, which needs your approval.

### 5. MySportsFeeds
- No free tier is stated. "Personal" pricing starts at $5/month per league, plus a free trial on request. **Excluded by the $0 budget.**

### 6. NFL.com: terms only
- Section 1.3: "Systematic retrieval of data... to create or compile... a collection, compilation, database... is prohibited absent our express prior written consent." **Not usable.**

### 7. Pro-Football-Reference: policy only
- Rate limit of 20 requests per minute, and they state they "can not provide the data available as a download" because of licensing. Also not a real-time schedule source. **Not usable.**

## Comparison

| | nflverse | ESPN API | TheSportsDB free | API-Sports free |
|---|---|---|---|---|
| Cost | $0 | $0 | $0 (but crippled) | $0 (account needed) |
| Full 2026 schedule | Yes | Yes | **No (15 events)** | Unverified |
| ID stable across a week change | **No** (verified) | Likely (not directly verified) | Likely | Unverified |
| TBD marked | **No** | Yes | Unverified | Unverified |
| Cancellation | **Row disappears** | Explicit status | `strPostponed` field | Unverified |
| Terms risk | Unclear (no license) | **High (prohibited)** | Low for dev | Unverified |
| Stability | Community-maintained, active | Can break without notice | Stable, documented | Documented |

**Design implication for any choice:** none of the free options gives a clean, permanent game identity *and* explicit TBD status under clear terms. FixtureFeed will probably need **its own permanent game ID**, matched to source records by rules (for example: same season, same two teams, same game type, plus source IDs when present). The ICS UID would come from our ID, not the source's. This is also what makes baseball doubleheaders and multi-source fallback possible later. This is architecture and needs your approval before I build it.

## Competitor comparison (public pages only)

| Product | Delivery | Changes handled | Notifications | Change history | Price |
|---|---|---|---|---|---|
| Sync2Cal | Calendar sync; delivery method not stated on homepage | "keeps it updated", no detail | Not mentioned | Not mentioned | Free + "Pro" (per search summary) |
| FanSync | App, manual "resync" (per search summary only; **fansyncsport.com did not resolve**) | Changes reach the calendar only on manual resync | Not verified | Not verified | Not verified |
| Calendar72 | Subscription feeds (Apple/Google/Outlook) | "reschedules and new fixtures sync on their own" | **Yes**, opt-in iPhone alerts (v1.11) | Not mentioned | Free |
| Sports Calendar Sync (iOS) | App writes events directly into Apple Calendar | "Update calendar events when match details change"; refreshes when app opened | Kickoff reminders only | Not mentioned | Free |
| SportsCal (not on your list) | ICS subscription feed | "flex changes... reflected live"; FAQ admits Google refreshes every 12–24h | Not mentioned | Not mentioned | $47/year |

**What this means for your differentiators:**
- **Notifications are not unique.** Calendar72 already offers change alerts for free.
- **A visible change history** wasn't mentioned by anyone I checked. That is the best remaining differentiator, but "not mentioned on a marketing page" does not prove they don't have it.
- SportsCal's FAQ confirms the client-polling limit (Google refreshes every 12–24h). Every competitor has this problem, so we can't win on freshness.

## Not done / not verified
- Did not observe a single source's ID before and after a real reschedule. That would need recording snapshots over time (a backlog idea, not approved).
- API-Sports free-tier season coverage.
- FanSync claims (site unreachable; only third-party summaries).

## Sources
- nflverse: https://github.com/nflverse/nfldata (DATASETS.md, data/games.csv)
- ESPN/Disney terms: https://disneytermsofuse.com/english/
- TheSportsDB: https://www.thesportsdb.com/documentation, https://www.thesportsdb.com/docs_terms_of_use.php
- MySportsFeeds: https://www.mysportsfeeds.com/feed-pricing/
- NFL.com terms: https://www.nfl.com/legal/terms/
- Sports Reference: https://www.sports-reference.com/bot-traffic.html
- Sync2Cal: https://sync2cal.com
- Calendar72: https://apps.apple.com/us/app/calendar72-sport-event-sync/id6762543906
- Sports Calendar Sync: https://apps.apple.com/us/app/sports-calendar-sync/id6763406189
- SportsCal: https://sportscal.io/nfl-ical
- API-Sports summary (third party): https://highlightly.net/blogs/best-nfl-apis-in-2026
