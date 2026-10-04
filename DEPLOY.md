# Proposal: $0 deployment (NOT approved; needs the director's decision)

Researched 2026-10-03 from public pricing pages and write-ups (sources at the end).
Nothing here has been set up: no accounts, no hosting, no spending.

## (1) What needs hosting

| Piece | Needs | Notes |
|---|---|---|
| Web app (`fixturefeed.web`) | HTTPS URL that answers calendar fetches fast | Google fetches feeds server-side every 12–24 h; a slow or sleeping server risks failed refreshes. |
| Ingest (`python -m fixturefeed.ingest`) | Run every ~30 min | One-shot command; doesn't need to live inside the web process. |
| Postgres | Small (our data is a few MB) | Must not expire. |

## (2) Why it matters
Decision #9 targets a deployed project by Nov 20, 2026. Google Calendar can only subscribe to a public HTTPS URL, so the live "event updates in place" demo needs this.

## (3) Options

### A. Vercel Hobby (web) + Neon Free (Postgres) + GitHub Actions schedule (ingest)  ← recommended
- **Web on Vercel Hobby:** free, no card, FastAPI supported as serverless functions. Cold start adds roughly 0.3–0.8 s, well within what calendar fetchers tolerate. 10 s function timeout (our feed renders in milliseconds). **Personal, non-commercial use only**, which fits.
- **Postgres on Neon Free:** 1 GB per project (raised on 2026-10-01), 100 compute-hours/month, scales to zero when idle and wakes in under a second. Doesn't expire.
- **Ingest on a GitHub Actions schedule** every 30 min, writing straight to Neon. Free and unlimited for public repos.
- **Code changes needed** (about 2–3 hours):
  - Use Neon's pooled connection string instead of our in-process pool, which doesn't fit serverless.
  - Move the rate limiter into Postgres, because each serverless instance would otherwise keep its own count.
  - Add an ingest workflow plus a migration step.
- **Risks:**
  - GitHub may delay scheduled runs by 5–30 minutes. That's harmless, since Google only re-fetches every 12–24 hours anyway.
  - **GitHub disables schedules in public repos after 60 days with no activity.** The season runs Sept–Feb, so this needs a reminder or a small keep-alive step.
  - Compute budget: 48 ingests a day, each waking the database for a few minutes, comes to an estimated ~30 of the 100 hours a month. **This is an estimate, not measured.**

### B. Render Free (web) + Neon Free + GitHub Actions schedule
- Runs our app as-is (a long-running process, so the pool and the rate limiter work unchanged).
- **The big risk:** the free web service sleeps after 15 min idle and takes about **1 minute** to wake. A calendar fetch that hits a sleeping server may time out, so subscriptions could silently stop updating. Pinging it to keep it awake works against the spirit of the free tier.
- Render's free Postgres **expires after 30 days**, so the database would still be Neon.

### C. Oracle Cloud Always Free VM (everything on one machine)
- An always-on VM runs the web app, the ingest loop (`--every 30`) and Postgres. No sleeping and no cold starts. Good server-operations experience.
- **Requires a credit card at signup** (it isn't charged), and you take on server upkeep: security updates, TLS certificates, backups. That's the most hours of the three.

### Ruled out
- **Koyeb:** its free plan is being withdrawn for new users after the Feb 2026 acquisition.
- **Fly.io:** no free tier for new organizations.
- **Google Cloud Run:** needs a billing account with a card.
- **Render Postgres:** expires after 30 days.

## (4) Recommendation
**Option A.** It's $0 with no card, it has no sleep problem for calendar fetchers, and every piece is a common, well-documented setup. The serverless adjustments are small and make good interview material: "why the rate limiter moved into Postgres".

## (5) Risks and cost
- **$0** on all options while inside free limits. Vercel Hobby and Neon Free stop service at their caps instead of billing.
- **Accounts you would create:** Vercel, Neon, and a GitHub repo (public, for free Actions minutes and CI).
- **The repo would be public.** That republishes the nflverse fixture (decision #20 already accepted this) and makes `DECISIONS.md`/`REVIEW.md` visible. That may be a plus for interviews, but it's worth deciding on purpose.
- **Effort:** about 2–3 h of code changes plus about 1 h of setup, which fits before Nov 20.

## Sources
- Render free tier: https://render.com/docs/free ; 30-day Postgres expiry: https://bex.co/blog/2026/09/23/render-free-postgres-30-day-expiry
- Neon free limits: https://neon.com/faqs/free-plan-limits-and-quotas
- Koyeb changes: https://www.srvrlss.io/provider/koyeb/
- Vercel Hobby limits and Python: https://vercel.com/pricing , https://kuberns.com/blogs/vercel-python/
- GitHub Actions schedules: https://cronuru.com/guides/github-actions-scheduled-workflows
- Google Calendar refresh behavior: https://usemooncal.com/en/guides/google-calendar-ics-refresh
