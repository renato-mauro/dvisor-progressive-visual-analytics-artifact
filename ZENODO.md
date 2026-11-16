# Archiving the GitHub release with Zenodo

The [GitHub repository](https://github.com/renato-mauro/dvisor-progressive-visual-analytics-artifact) holds the experiment code. Keep the
article-compatible observation archive and its checksum with the corresponding
GitHub release. DVISOR hosts the Parquet inputs and metadata, and the README
and experiment configurations record the download links.

To build the observation archive from the original collection, run
`python scripts/package_zenodo_results.py` from the repository root. The
outputs are `release/experimental-observations-v1.0.0.zip` and its `.sha256` file.
Use the article's original 123 runs, including the three Phase-1 warm-ups.

Enable the public repository in Zenodo's
[GitHub integration](https://help.zenodo.org/docs/github/), then archive the
versioned source release. Confirm that the DOI for that version resolves
publicly before adding it to the manuscript and `CITATION.cff`. See
[GitHub's citation documentation](https://docs.github.com/en/repositories/archiving-a-github-repository/referencing-and-citing-content).
