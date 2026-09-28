"""What both sides agree on BEYOND the A2A spec. The spec itself (types, states, methods) now comes from the
official SDK, which the Service Desk and the IAM team each install — pinned to the same version.

⚠️ The only extra agreement: the (naive) header that says who the user is. Lesson 2.5 replaces it with a
signed token."""

USER_HEADER = "x-user-email"
