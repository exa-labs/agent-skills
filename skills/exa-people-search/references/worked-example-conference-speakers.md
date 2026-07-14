# Worked example — embedded-Rust conference speakers

A complete Step-1 search plan for a brief that has nothing to do with hiring: an organizer
putting together a speaker lineup. Use it as a model for how to turn any "find me people who…"
brief into a plan — note that the segments aim at the *venues where matching people are visible*
(open-source projects, product teams, past conference schedules, technical writing), and the
`exclude_org` keeps the organizer's own company off the list.

The brief: *"I'm organizing an embedded-Rust conference in Europe. Find speakers: people who
actually ship Rust on microcontrollers or in firmware, and who have some evidence they can talk
about it publicly. We work at Ferrous Systems, so skip our own people — we know them already."*

```json
{
  "objective": "Speakers for an embedded-Rust conference: practitioners who ship Rust on microcontrollers or in firmware and have public speaking or writing evidence",
  "locations": ["Europe"],
  "exclude_org": "Ferrous Systems",

  "must_haves": [
    "Hands-on Rust experience in embedded systems, firmware, or bare-metal contexts (production work or a significant open-source project).",
    "Public evidence of communicating technical work: a conference or meetup talk, substantial technical blog, podcast appearance, or well-documented project."
  ],
  "signals": [
    "Maintainer or significant contributor to an embedded-Rust ecosystem project (embassy, RTIC, probe-rs, an embedded-hal driver).",
    "Shipped Rust firmware in a commercial product.",
    "Prior talks at systems or Rust conferences (RustConf, Oxidize, FOSDEM, embedded meetups).",
    "Writes accessibly about low-level topics for a broad audience."
  ],

  "dimensions": [
    {"key": "embeddedRustDepth",   "scale": "capability"},
    {"key": "publicCommunication", "scale": "capability"},
    {"key": "productionShipping",  "scale": "capability"},
    {"key": "openSourceFootprint", "scale": "strength", "extra": ["projects"]},
    {"key": "communityStanding",   "scale": "strength"}
  ],

  "segments": [
    {"label": "oss_maintainers",    "focus": "Maintainers and top contributors of embedded-Rust ecosystem projects: embassy, RTIC, probe-rs, esp-rs, nrf-hal, stm32-rs, and widely used embedded-hal drivers; check GitHub activity and project docs for who actually does the work."},
    {"label": "product_firmware",   "focus": "Engineers shipping Rust firmware in commercial products at companies like Espressif, Oxide Computer, Memfault, 1Password (hardware), Sensirion, and embedded consultancies; look at engineering blogs and team pages."},
    {"label": "conference_circuit", "focus": "People who have already given talks on embedded Rust or adjacent low-level topics at RustConf, Oxidize, FOSDEM, EuroRust, RustFest, or local Rust meetups; check published schedules and recorded-talk listings."},
    {"label": "writers_educators",  "focus": "Authors of substantial embedded-Rust writing: the Rust Embedded Working Group book contributors, popular tutorial series authors, course creators, and technical bloggers who cover microcontroller Rust in depth."}
  ]
}
```

## What changes for other kinds of briefs

The plan shape is always the same; what varies is where the segments point:

- **Advisors / experts** (e.g. "clinical-NLP researchers for an advisory board") — segments point
  at research groups, PubMed/Scholar author lists, workshop program committees, and industry labs;
  `profileUrl` will mostly be Scholar or lab pages, and `fiber_ai` adds little.
- **Podcast or panel guests** (e.g. "founders who have written about pricing") — segments point at
  founder blogs, podcast guest archives, newsletter authors, and conference lineups; weight the
  communication dimension `capability`, not `strength`.
- **Business people** (e.g. "VPs of Supply Chain at mid-size EU manufacturers") — closest to the
  sibling candidate-sourcing skill; segments point at industries and company tiers, LinkedIn
  matters most, and attaching `fiber_ai` (if the account has Exa Connect) helps.

## Notes

- Four segments fit *this* brief because embedded-Rust people are visible in four genuinely
  different venues. A narrower ask ("find the 5 most active embassy contributors who have given
  a talk") would be a 1-segment plan with a small target — size the fan-out to the brief, don't
  reproduce this shape.
- The `exclude_org` mechanism is optional and orthogonal to the criteria: use it whenever "not
  from X" is part of the brief (the requester's own org, a competitor, a sponsor).
- If the brief has no location constraint, leave `locations` empty; the location bonus and
  penalties then switch off (see `scoring-and-calibration.md`).
