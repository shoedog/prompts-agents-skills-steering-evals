# access.can_access

`can_access(user, resource)` decides whether `user` may read `resource`.

Rules:
- Admins (`user.is_admin is True`) may access ANY resource.
- A non-admin may access a resource ONLY if they own it
  (`user.id == resource.owner_id`).
- Everyone else is denied.

`user` has `.id` (int) and `.is_admin` (bool); `resource` has `.owner_id`
(int). Return True to allow, False to deny.
