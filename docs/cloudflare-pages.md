# Deploy on Cloudflare Pages

This repository is ready to build the ApkPy documentation with Cloudflare Pages while keeping the source repository private.

## What becomes public?

The build runs MkDocs and creates <code>site/</code>. Cloudflare publishes that generated directory only.

The following are **not** inside the published directory:

- the private ApkPy package or compiler source;
- the Git history;
- databases, local keys or development artifacts;
- the Markdown source files themselves as raw repository files.

!!! warning "Do not put secrets in documentation"
    Anything written in <code>docs/</code> can appear in the generated website. Never commit API keys, PyPI tokens, OAuth client secrets, signing keys or private customer information.

## Cloudflare project settings

In **Workers & Pages**, choose **Create application → Pages → Connect to Git**, authorize GitHub and select this repository.

Use these exact settings:

| Setting | Value |
| --- | --- |
| Production branch | <code>main</code> |
| Framework preset | <code>None</code> |
| Root directory | leave empty |
| Build command | <code>python -m pip install -r requirements-docs.txt && python -m mkdocs build --strict</code> |
| Build output directory | <code>site</code> |

No environment variables or secrets are required for the documentation build.

## Limit GitHub access

When installing the **Cloudflare Workers & Pages** GitHub App:

1. choose **Only select repositories**;
2. select only <code>apkpy-project/repo-apkpy</code>;
3. do not grant access to unrelated private repositories.

Every push to <code>main</code> triggers a production build. Pull requests and other configured branches receive separate preview URLs.

## Make the documentation private

A private Git repository does not automatically make the generated website private. By default, anyone with the Pages URL can read the published site.

To restrict the website:

1. connect a custom domain such as <code>docs.example.com</code> to the Pages project;
2. open **Zero Trust → Access controls → Applications**;
3. create a **Self-hosted** web application for that hostname;
4. add an **Allow** policy for the permitted email addresses or email domain;
5. verify in a private browser window that the login page appears before the documentation.

Cloudflare Access is deny-by-default once the protected application and policy are active. Keep at least one owner email in the Allow policy to avoid locking yourself out.

## Test the same build locally

From the repository root:

~~~ powershell
python -m pip install -r requirements-docs.txt
python -m mkdocs build --strict
python -m mkdocs serve
~~~

Open <code>http://127.0.0.1:8000</code>. The strict build fails on invalid navigation entries, missing files and several classes of broken link, so it should also be used in Cloudflare.

## Deployment checklist

- [ ] The repository selected in Cloudflare is the intended private repository.
- [ ] GitHub App access is limited to that repository.
- [ ] The build command finishes successfully.
- [ ] The output directory is exactly <code>site</code>.
- [ ] No token, key or private file appears in the build output.
- [ ] If the site must be private, Cloudflare Access was tested while signed out.

## Official references

- [Cloudflare Pages Git integration](https://developers.cloudflare.com/pages/get-started/git-integration/)
- [Cloudflare Pages GitHub integration and repository access](https://developers.cloudflare.com/pages/configuration/git-integration/github-integration/)
- [Cloudflare Access for web applications](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/)
