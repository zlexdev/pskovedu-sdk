# protocol/

Wire-protocol abstraction layer for the pskovedu SDK.

## Design

A ``BaseMethod[T]`` declares *intent* (endpoint, returning type, args). The
actual wire encoding lives here — method-classes never know how to serialise
themselves; they just declare class-vars.

The session funnel calls:
1. `protocol.build_request(method, config, host)` → `PreparedRequest`
2. transport sends it
3. `protocol.decode_response(method, raw)` → `T`

## Files

- `base.py` — `Protocol` ABC (`build_request` / `decode_response` / `is_idempotent` /
  `validate_subclass`); `PreparedRequest`; `RawResponse`; re-exports `ProtocolError`.
- `rest.py` — `RestProtocol` (default): resolves `__url__` path templates, routes
  fields by verb (bodyless → query; body verbs → JSON body), decodes JSON →
  `model_validate`, `HtmlParsed` subclass → raw text passthrough.
- `ext_direct.py` — `ExtDirectProtocol`: `{action, method, data, type:"rpc", tid}`
  envelope; REMOTING_API arg-count validation; exception envelope detection.
- `x1.py` — `X1Protocol`: `/x1db/service/call`; NAME→GUID resolve via registry.
- `sse.py` — `SseProtocol`: `text/event-stream` → `EventStream[T]` async iterator.

## Protocol class-vars by type

| Protocol | Required class-vars on method |
|---|---|
| RestProtocol | `__http_method__`, `__url__` |
| ExtDirectProtocol | `__action__`, `__rpc_method__`, `` |
| X1Protocol | `__x1_service__`, `__x1_method__`, `__x1_model__` |
| SseProtocol | `__url__`, `__event_model__`, `__terminal_event__` |
