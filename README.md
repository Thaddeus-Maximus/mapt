# mapt
Organize resources by where they are.
Inspired by a nifty directory tool I've used, but intended to be better, and opensource.

# Real objects
- A `pin` has a `type`, `name`, `picture`(s?), `description`, and `coordinates` in its associated `area`. The pin can be a special type, which is an `area`.
- An `area` has within it more `pin`s and the `picture` is used to show a layout of the area.
- `type` is used to categorize `pin`s; e.g. a type could be a Person (their desk), a Printer, a Tool, a Cabinet...
 
- I don't know if areas are pins, or pins _point to_ areas... I think the former is actually easier. There's plenty of cases in which we want both, some cases in which we want just areas, and no cases in which we want just non-areas. And their behaviors are the same.

- Yes, this means that areas are recursive. So, you could make a pin for a shelf, then within that shelf, make pins for particular items on the shelf.

- One of the `area`s must be demarkated as the top-level. I think? I guess that would just be the one with its parent `area` set to null.
- Maybe user-masking will become a thing at some point


# Auth objects
- Just one level for now: admin

# Interactions
- Search pins by name
- Search pins by content (eventually)
- "Enter" an area
- "Leave" an area (back up a recursion)
- CRUD areas
  - Note that changing the picture/layout of an area should prompt something to be done about the pins
- CRUD pins
  - Placing the pin on the appropriate area will require some UX thought
