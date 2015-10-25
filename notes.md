CLI tool to sync time entries from Toggl to Freckle.

1. Usage: froggle START_DATE [END_DATE]
2. froggle fetches all time_entries from Toggl
3. froggle fetches all projects from Freckle
4. For each time entry, if project is seen for the first time, asks the user which Freckle 
   project corresponds to this time entry's project and caches the result.
5. froggle creates a time entry in Freckle.
