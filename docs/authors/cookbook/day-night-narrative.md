# Cookbook: Day-Night Narrative

This recipe shows how to write adventure text that changes based on the current time of day, season, and calendar functions available in Oscilla's template system.

The engine's `today()`, `hour()`, and `season()` functions read from the real-world clock, making narrative feel alive without any persistent state.

---

## Basic Time-of-Day Text

Use `hour()` (returns 0–23) in a Jinja2 conditional:

```yaml
- type: narrative
  text: |
    {% if hour() < 6 %}
    The village is dead quiet. A handful of torches flicker along the main street.
    {% elif hour() < 12 %}
    The morning market is setting up. Merchants call out greetings.
    {% elif hour() < 18 %}
    Midday bustle. Children run between the stalls.
    {% else %}
    Lanterns glow in windows. Most shops are closing for the night.
    {% endif %}
```

---

## Season-Aware Descriptions

Use `season()` — returns `"spring"`, `"summer"`, `"autumn"`, or `"winter"`:

```yaml
- type: narrative
  text: |
    The forest path is
    {% if season() == "spring" %}
    carpeted in wildflowers. Birdsong fills the air.
    {% elif season() == "summer" %}
    dry and dusty underfoot. Insects buzz in the midday heat.
    {% elif season() == "autumn" %}
    thick with fallen leaves that crunch with every step.
    {% else %}
    blanketed in snow. Your breath fogs in the cold.
    {% endif %}
```

---

## Conditional Adventures by Time

Pool conditions can also use templates — but only when the condition uses a stat. For time-based availability, the simplest pattern is to gate it in the adventure text rather than the pool.

If you want a truly time-conditional adventure — one that simply doesn't appear at night — write a `stat_check` as the first step using a condition that always passes but delivers time-appropriate text, and use `end_adventure` in the fail branch:

A simpler approach is to put the time check in the adventure's opening step and redirect with `goto`:

```yaml
steps:
  - label: daytime-check
    type: stat_check
    condition:
      type: character_stat
      name: some-always-true-stat    # placeholder technique
      gte: 0
    on_pass:
      steps:
        …
```

The most authoring-friendly approach is just to write branching narrative. Players experience a coherent world even when the same adventure runs multiple times at different hours.

---

## Farming and Seasons

Seasonal content works naturally for agricultural worldbuilding:

```yaml
- type: choice
  prompt: "What's growing in the fields?"
  options:
    - label: "Check the crop"
      steps:
        - type: narrative
          text: |
            {% set s = season() %}
            {% if s == "spring" %}
            The fields are freshly sown. Nothing to harvest yet.
            {% elif s == "summer" %}
            Wheat stands tall. The harvest will be good this year.
            {% elif s == "autumn" %}
            The last of the harvest is being brought in. Workers wave from the carts.
            {% else %}
            The fields lie fallow under frost. The earth rests.
            {% endif %}
```

---

## Date-Based Events

Use `today()` — returns an ISO date string (`"2025-06-15"`):

```yaml
- type: narrative
  text: |
    {% set d = today() %}
    {% if d[5:7] == "12" and d[8:10] == "25" %}
    The village is decorated for the winter festival. Children carry candles.
    {% else %}
    The square looks much as it always does.
    {% endif %}
```

`today()` slices: `d[5:7]` is month, `d[8:10]` is day.

---

## Notes

- All template functions are read-only. They observe the real system clock.
- The `season()` function follows the standard Northern Hemisphere meteorological seasons: spring Mar–May, summer Jun–Aug, autumn Sep–Nov, winter Dec–Feb.
- Template evaluation happens at step render time — if a player runs the same adventure twice in the same session hours apart, the text may differ.

---

*See [Templates](../templates.md) for the full function and filter reference.*
