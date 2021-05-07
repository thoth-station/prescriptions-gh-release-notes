Prescriptions for GitHub release notes
--------------------------------------

Automatically construct prescriptions for linking GitHub release notes based on
`thoth-solver <https://github.com/thoth-station/solver>`__ results.

Visit `prescription documentation for more info
https://thoth-station.ninja/docs/developers/adviser/prescription.html#githubreleasenoteswrap`__.

Running data aggregation
========================
If you wish to
develop this job, check `thoth-station/datasets repository
<https://github.com/thoth-station/datasets>`__ sharing some solver results that
can be used with this job.

.. code-block:: conosle

  git clone https://github.com/thoth-station/prescriptions-gh-release-notes-job  # or use SSH
  cd prescriptions-gh-release-notes-job
  pipenv install --dev
  pipenv run python3 ./app.py
