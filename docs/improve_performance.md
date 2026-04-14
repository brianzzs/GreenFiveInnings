# Goal:

We are aiming to increase the performance for the Weather endpoint.

# Current Problem:

- The GET request on /park-factors endpoint is taking 9s to complete. 
- Sometimes the RAM is spiking to 2gbs, the usage itself is high already around 800mb, but spiking to 2gb seeems bad.
- GET Request on /comparision is taking almost 9s.



# Acceptance Criteria

-We need to achieve the goal of reducing RAM usage
-/park-factors endpint answer under 5s.
-/comparision endpoint answer under 4s.

# Suggestion:

- Maybe we can have functions and stuff running asynchronously.


