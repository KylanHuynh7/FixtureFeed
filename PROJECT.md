# Project context

Project name: FixtureFeed. Keep the display name in a single config constant so a rename stays cheap.

I am a university student (UC San Diego, Data Science) building a software engineering project for internship applications.

Concept: a subscribable sports calendar. Users pick teams and filters and receive a private ICS feed URL that calendar apps subscribe to. Games that are moved, flexed, or postponed should update the existing calendar event instead of duplicating it.

Competitive landscape (known, so do not pitch this as novel): similar products exist, including Sync2Cal, FanSync, Calendar72, and Sports Calendar Sync. The value of this project is engineering depth and provable correctness on schedule changes. My intended differentiators are a visible change history and change notifications, but I have not verified what competitors offer.

Considerations to evaluate, not decisions: calendar clients poll on their own schedule, so freshness is limited; rescheduled games need stable UIDs and SEQUENCE numbers; the schedule data source may be unofficial and unstable; possible differentiators are filters, merged multi-team feeds, change notifications, and a change history.

Future sports order (not in scope now): baseball, basketball, hockey. Do not build for them yet, but flag any design choice that would make them hard. Example: baseball has doubleheaders, so identity must not assume one game per team per day.

My stack: Python is my strongest language.

Hours per week: roughly 8-10, possibly more right now. Plan on the lower number.

Target dates: MVP running locally by Oct 23, 2026; polished and deployed by Nov 20, 2026.

Budget: strictly $0. No paid APIs, services, or plans.

## Still open (all mine, not yet decided)
Web framework (you may recommend FastAPI, but it is NOT approved), whether to use Docker for local Postgres, ICS generation approach (hand-built vs. a library), Python version and package manager, project structure, hosting (deferred until MVP works locally).
