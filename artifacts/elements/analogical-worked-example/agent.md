---
name: analogical-worked-example
description: Route here to solve a task that resembles a known, previously solved problem.
---
When a task resembles a solved problem, lay out one worked case of the same shape and map its steps onto the task before adapting.

Example — reverse a singly linked list:
1. Track prev=null, curr=head.
2. Each step: save next=curr.next; set curr.next=prev; advance prev=curr, curr=next.
3. Stop when curr is null; return prev.

Reuse the structure — moving parts, per-step transform, stop condition — for the task at hand.
