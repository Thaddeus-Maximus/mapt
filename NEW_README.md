*Like DEKA's directory tool but better and including inventory management*

I called this `mapt` once upon a time - had the idea but never got made

# Basic Problem
You've got a bunch of things but you don't know where they are and you want people, new people, to find them easily

You want to keep track of what tools you have
You want to keep track of when we bought consumables; how often we go through them
You want to keep track of who owns a particular item, perhaps

# Data Structure / Concepts

### Place
A place is where something resides. Places have:
- Parent places (maybe)
- Name
- Description
- Map

### Virtual Place
A virtual place is something like a toolbox. It shows up on a place like a Thing, but it contains several Things. This keeps the interface from getting too clutterred. It can easily be upgraded to a full Place by adding a map (maybe this isn't a special category; it's just a place without a map)
### Thing
Every thing gets its own markdown file. It can have free prose notes. Things have:
- Name
- Description
- Place where it is
- Location (coords) in that place
- Date added
- Quantity on hand

# Interface

The primary interface is as a map with location tags on it with a side pane for the highlighted tag. Clicking the edit button on the side pane would allow editing.

On mobile, it would alternate between map and detail view.

# Architecture / backend

Files should be predominantly `.md` files; as if it could be opened in obsidian. it would be ok to make an index (e.g. with sqlite3) though.

Follow similar patterns as grazr.