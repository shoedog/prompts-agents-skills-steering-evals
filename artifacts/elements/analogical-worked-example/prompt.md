Here is one solved case of the same shape. Map its steps onto this task, then adapt.

Example — reverse a singly linked list:
1. Track prev=null, curr=head.
2. Each step: save next=curr.next; set curr.next=prev; advance prev=curr, curr=next.
3. Stop when curr is null; return prev.

Reuse the structure — moving parts, per-step transform, stop condition — for the task at hand.
