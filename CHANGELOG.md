# Change Log

## 0.3.0

[Full Changelog](https://github.com/jayvdb/dns-cache/compare/0.2.0...0.3.0)

**Implemented enhancements:**

- Add dnspython 2 support
- `ExceptionCachingResolver`: Cache authority and additional sections ([dcadbb](https://github.com/jayvdb/dns-cache/commit/dcadbb))
- `HostsCache`: Add preloaded hosts (e.g. `/etc/hosts`) cache ([fc9ec2](https://github.com/jayvdb/dns-cache/commit/fc9ec2))

**Fixed bugs:**

- ExceptionCachingResolver: Do not cache `NoMetaqueries` ([5f571e](https://github.com/jayvdb/dns-cache/commit/5f571e))
- Fix patched `socket.gethostbyname` to resolve names in `/etc/hosts` ([issue 11](https://github.com/jayvdb/dns-cache/issues/11))

**Other:**

- Update tests to handle changes in Google DNS behaviour
- Many more tests
- Testing against many U.S. DNS servers

## [0.2.0](https://github.com/jayvdb/dns-cache/tree/0.2.0) (2020-03-09)
[Full Changelog](https://github.com/jayvdb/dns-cache/compare/0.1.0...0.2.0)

- Support Python 3.4
- Enhanced tests

## [0.1.0](https://github.com/jayvdb/dns-cache/tree/0.1.0) (2020-03-08)

- Initial release
