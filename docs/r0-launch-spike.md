# R0 起動方式の比較・検証候補

状態: 未受入の設計候補。Owner: #3。実装仕様の確定ではない。

## 目的と方式

- Hubの最上位文書を専用のmanifest scope内に維持し、URLバーを伴うトップレベル遷移を通常利用から排除する。
- iframeによる全表示領域利用を第一候補とする。ただし同一origin iframeは隔離ではない。合成fixtureの同一origin/opaqueと別origin/storageの2方式を比較する。実サイトのorigin、sandbox、許可API、認証、動作確認をアプリ単位で記録する。
- 同一originでscriptsとsame-originを同時許可する方式を隔離とは扱わない。信頼境界を別originに移せない場合は、同一信頼域の明示的受入と要件検証が必要。未信頼コンテンツは拒否する。
- 同一originの広いmanifest scopeはトップレベル遷移でもブラウザUIを抑え得る比較候補だが、Hub復帰・別PWAのscope重複・外部originを解決しない。Service Workerのscopeとmanifestのscopeは独立。
- 直接統合は既存の明示的なモジュール契約を使用する場合のみ検討。リポジトリ一括改修やreverse proxyによるヘッダー迂回を前提としない。
- 非対応は明示的外部起動へ縮退。自動トップレベル遷移や任意URLの埋込をしない。

## 代表検証

`spikes/r0_frame_probe.py` はloopback上の合成fixtureのみ。縦横viewportで入力、localStorage、親DOMへのアクセス拒否、top URL不変、iframe領域、復帰を確認する設計。別originを別ポートで表現しており、別サイトのCookie/Storage分離を再現するものではない。実行前提は許可された通常のChromium環境とPlaywright。

先行fixtureのローカル起動は net::ERR_BLOCKED_BY_ADMINISTRATOR で停止し、テスト未実行。このbranchの試作は未検証。管理ポリシーの迂回は行わない。外部公開URLはweb toolがアクセス不能、ローカルDNSも失敗。これらはサイト障害の証拠ではない。

次の確認: 許可された実行環境で合成fixtureを実行、公開URL/HTTP/ヘッダー/実機を別々に確認する。音声、入力・ファイル、タッチ、保存、画面回転、復帰、許可拒否、iOSホーム画面からの起動とブラウザURLバーを実サイトで観測する。ヘッダーやloadイベントだけで機能を保証しない。iOS status barを消すこととURLバーを消すことは別要件。

## 共通化

Site Kitの既存検索・lifecycle・optional loaderの契約を調査済み。安定配布・実機受入は別Owner。ランチャー固有データ/起動状態はHub、複数サイトで同じ意味の共通機構はSite Kit等の既存Ownerとの境界を検証後に決定。Repo Monitorの公開devflow状態投影はアプリ台帳とは異なる。既存repoへの展開は非目標。

## 根拠

- [R0の調査記録](https://github.com/kinoko34077/kinotch-hub/issues/3)
- [MDN iframe](https://developer.mozilla.org/ja/docs/Web/HTML/Reference/Elements/iframe)
- [WebKit Safari 26.0](https://webkit.org/blog/17333/webkit-features-in-safari-26-0/)
- [WebKit bug 280181](https://bugs.webkit.org/show_bug.cgi?id=280181)
