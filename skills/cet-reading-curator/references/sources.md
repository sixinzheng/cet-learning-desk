# Source and provenance policy

## Allowlist

- Xinhua English: `english.news.cn`, `www.news.cn`, `news.cn`
- The State Council English site: `english.www.gov.cn`, `www.gov.cn`
- China Daily: `global.chinadaily.com.cn`, `www.chinadaily.com.cn`, `chinadaily.com.cn`
- CGTN: `news.cgtn.com`, `www.cgtn.com`, `cgtn.com`

Use HTTPS only. Revalidate every redirect. Resolve hosts and reject loopback, private, link-local, multicast, reserved, and unspecified addresses. Limit response size, content type, redirects, time, and request rate.

## Acquisition

1. Discover recent candidate links from an allowlisted listing page.
2. Select a candidate whose title and facts fit one canonical topic: `健康`, `教育`, `文化`, `环境`, `社会`, or `科技`.
3. Record source name, final URL, source title, publication date, and retrieval time.
4. Extract only a bounded fact brief for generation. Do not store the source article body in the reading database.
5. Reject paywalls, login gates, non-HTML downloads in the automated path, missing factual text, unsupported domains, duplicate URLs, and uncertain provenance.

## Copyright-safe transformation

The generated exercise is a new instructional text based on verified facts. Change organization, emphasis, transitions, and sentence construction. Reject any generated passage sharing eight consecutive source words. Attribution describes the source as `题材参考`; it does not imply endorsement or republication rights.
