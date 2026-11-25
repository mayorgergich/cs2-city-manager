# How the city makes its living: economy archetypes

The founding chat asks the Mayor what kind of city they want and stores one of these ids as `economy` in
the city's charter (`<city>/manager/charter.md`, or `founding.md` in an older city), or two joined with `+` when the Mayor wants both (`"industry+commerce"`: read both
sections and § Combining). The plan follows it: the zoning mix, where things go, and what the roads must carry. The id
is a starting point, not a cage: the Mayor's own words in `notes.economy` win where they disagree with it, and with
unlimited money (`options = ["unlimited money"]`) the money advice below matters little.

The numbers are starting points read from the game's code (1.6) and from one city played through in 2026: change one
lever at a time and watch what happens. Taxes, fees and budgets are the Mayor's to set; you suggest.

| id | In one line for the Mayor |
|---|---|
| `balanced` | A bit of everything; taxes at 10%; zoning follows demand. The safe default |
| `industry` | An industrial and export city: factories, warehouses, freight by rail, port and highway |
| `commerce` | A commerce and office city: shops along the main roads, offices, an educated workforce |
| `dense` | Dense and highly taxed: apartments, mixed use, transit first |
| `affluent` | Affluent and expensive: premium low-density homes, parks, high-wage jobs |
| `welfare` | High taxes paying for generous services everywhere |
| `user-pays` | Moderate taxes, with utilities paid through higher fees |
| `lean` | Low taxes and lean services, growing on volume |
| `tourism` | A tourist and leisure town: attractions, hotels, a waterfront, an airport |

## Phase one is the same for everyone

Until net income has been positive for a day and there are 1,000–2,000 residents:
- **Taxes** at 10% everywhere (the neutral point); industrial 8–9% if industry is short of workers.
- **Utilities:** essentials only, at full budget. Build fewer buildings rather than running them at a low budget: the
  budget slider is steep (measured: 70% budget gave 64% efficiency, 60% gave 46%, 50% gave 25%).
- **Zoning:** what demand supports, with a few empty lots. Homes and jobs grow together: industry stalls without
  workers, and growth is limited by households moving in, not by buildings.
- **Defer the expensive buildings.** Reserve land for the rail station, cargo terminal and port, but build them when
  income can carry them: in one city they cost more than everything else together in the first days.
- **Milestones pay cash and unlock pieces:** plan the first phase with unlocked pieces, and say what the next milestone
  brings (`city.py catalogue`).

The archetype's own levers come in from phase two, one at a time.

## The archetypes

### `balanced`
- **Zone:** what demand asks for: homes, shops along collectors and arterials, some industry by the highway.
- **Roads:** a plain hierarchy; one jobs district near the highway's entry, homes on the far side of downtown.

### `industry`
- **Earns:** industrial and commercial taxes, and residential tax from a mostly lower-skilled workforce.
- **Zone:** industry 25–35% of zoned land, in belts on the side away from homes, with buffers; homes for the workforce;
  shops for local needs; offices later (office demand grows with industrial output).
- **Specialised industry** on its resources, as whole chains (extractors, processors, shops): local demand is what
  keeps them going. Oil and ore run out.
- **Roads:** freight routes from the industrial belt straight to the highway interchanges, the cargo rail terminal and
  the port, with trucks kept off residential streets. Superblocks in the belt. Reserve the cargo terminal and the
  harbour early.
- **Taxes:** industrial 10% or less (it's the most sensitive: each point up costs demand and makes companies leave);
  residential 11–13%; commercial 10–12%.
- **Watch:** industrial demand against the workforce, pollution near homes, unemployment.
- **Traps:** raising industrial tax to pay for services; pollution next to homes; offices pay the industrial rate.

### `commerce`
- **Earns:** commercial tax on revenue (strong), office tax, residential tax from educated workers.
- **Zone:** shops along arterials and at transit stops, offices once unlocked, homes for an educated workforce; some
  industry still, because office demand follows industrial output.
- **Roads:** commercial frontage on the arterials, a dense centre, transit corridors to the offices.
- **Services:** education at full budget or more (graduation follows efficiency; the highest level only comes from the
  city's own universities), transit, telecom.
- **Taxes:** commercial 11–13%; office and industrial 10% or less; residential 11% or less (educated residents mind
  each point more).
- **Traps:** offices stall without industry; over-taxing educated residents.

### `dense`
- **Earns:** many residential taxpayers per lot, and commercial revenue.
- **Zone:** high-density homes (needs the unlock), mixed use, commercial.
- **Roads:** strong arterials, and **transit corridors kept free from day one** (tram or subway access is the biggest
  boost to land value); pedestrian links; short blocks downtown.
- **Taxes:** residential 12–15% paid for with happiness (each point costs household demand); commercial 11–13%;
  industrial and office 10% or less. Parks, telecom, mail, health, garbage and safety at full budget; no homelessness.
- **Watch:** residential demand above 20, happiness above 50, empty homes, homelessness. Under 45 happiness, demand
  turns negative; under 28, households leave within a day.

### `affluent`
- **Earns:** residential tax on high wages, and commercial revenue. Rent isn't city income.
- **Zone:** low-density premium homes on bigger lots, parks, shops close by, offices and high-tech for high-wage jobs.
- **Roads:** quiet curving local streets, tram or subway corridors (they raise land value most), commercial streets,
  green buffers. Industry far away and on the far side from homes.
- **Taxes:** residential 10–11% at most; commercial 11–12%; office and industrial 10% or less. Education up to
  university; full coverage at full budget.
- **Watch:** high-rent warnings, people leaving for lack of money, stalled level-ups, the education mix.
- **Traps:** a small population pays less tax in total; premium land needs high-wage jobs to fill it.

### `welfare`
- **Earns:** high residential and commercial taxes, spent on services that keep people happy enough to stay.
- **Zone:** mixed, medium density, with service buildings in every district.
- **Roads:** transit corridors, service sites in every district, walkable centres.
- **Taxes:** residential 13–16% only while happiness stays at 55 or more; commercial 11–13%; industrial and office
  10–11% at most. Education fees 0; healthcare a tiny fee, never exactly 0; free transit on key lines.
- **Traps:** services raise land value, so rents rise; taxing industry to pay for services; deficits.

### `user-pays`
- **Earns:** utility and garbage fees on top of taxes at 9–10%.
- **Levers:** electricity and water fees above the default, raised a step at a time while watching wellbeing, company
  efficiency and demand. Fees hit companies too.
- **Roads:** no special needs: a plain hierarchy.

### `lean`
- **Earns:** volume: taxes at 5–8% lift demand for homes and companies.
- **Services:** essentials only, at full budget; cut whole buildings, not budgets.
- **Roads:** build little and late; every kilometre is upkeep. No expensive rail or big plants early.
- **Watch:** net income still at or above zero, crime, telecom and mail backlogs, school coverage.

### `tourism`
- **Earns:** commercial tax on tourist spending, and hotels. A supplement rather than a base.
- **Levers:** a few big attractions by the shore, forest or heights; signature buildings; parks kept up; hotels for half
  the tourists or more; an **airport and a passenger harbour**, which bring most visitors.
- **Roads:** a waterfront promenade, scenic routes, transit to the attractions, land reserved for the airport and a
  passenger harbour; tourist traffic kept apart from freight.
- **Watch:** attractiveness, tourists against hotel rooms, crime near attractions.

## Combining

| Combination | Verdict |
|---|---|
| `industry` + `welfare` | Works if homes and shops carry the tax, not industry |
| `commerce` + `affluent` | A natural pair: educated workers, high wages, premium homes |
| `dense` + `welfare` + transit | A natural pair |
| `tourism` + `affluent`, or `tourism` + `commerce` | Good: tourists feed shops; affluent areas pair with scenery |
| `affluent` + `pace = "fast"` | **Conflict:** premium homes fill slowly; ask which matters more |
| `industry` + "no pollution" in `avoid` | **Conflict:** offer clean industry and offices instead of heavy industry |
| `lean` + generous services | **Conflict:** a deficit; one of them has to give |
| `affluent` + industry near homes | **Conflict:** pollution hurts health and housing quality |

Name each conflict plainly, recommend a way through, and let the Mayor choose.
