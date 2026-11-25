# R2 公開カタログ取得（収集・配信）

Owner #5。配信形状は docs/CATALOG_CONTRACT.md と schema v1。既存ホーム画面の外観を維持し、データ供給のみ接続する。

- 公開 REST /users/kinoko34077/repos の所有repoのみ。既存Actionsの一時read-only tokenは固定GitHub公開一覧APIのみへ送信（token未設定時は匿名）。公開性再確認・出力の最小化・redirect拒否を維持。公開サイト・旧版取得・配信成果物へtokenを送らない。Link全ページを devflow_mapped_read.github_pages.read_linked_rows へ委譲。10ページ×100件は現規模に対する安全予算であり、next残存は失敗。固定版の既存checkoutを CI で参照する（共通供給機構は既存Ownerの受入後に切替、Hub独自loaderなし）。
- 公開性・所有者・ID・重複を厳格に確認、最小フィールドへ投影。公開API応答自体が原子的ではない。非公開/不正行の混入や一覧途中障害は全体失敗、公開成果物を上書きしない。
- Pages有効の標準パスを候補とし、実HTTPと公開manifest（同じrepoパス内のstart_url、name/short_name）またはHTMLのapplication-nameで公開アプリの正の証拠を得る。manifestのdisplayは収録条件にしない。単なるPages有効・HTTP 200だけでは自動収録しない。明示済みの例外は安定repo IDとkeyで登録し、実HTTPで確認。複数app、Pages外の明示公開URLを汎用external定義で扱う。Hub自身は再帰起動を除外。archivedのみでは除外しない。repo一覧は公開確認済みのみ。
- 通信境界の正本は catalog/publication-network.json（現行外部宛先は既存Standby URLのみ）。標準Pages origin/所有repoパスは既存契約を維持。external定義の公開根拠と通信先を分離し、アプリ個別の起動許可とは扱わない。収集器・ブラウザadmission・CSPを同期し、python tools/collect_catalog.py --sync-network-assets で派生箇所を生成、CIで一致検証。追加宛先のDNS/redirect/秘密URL対策・所有根拠・所定承認は別工程。redirect拒否、資格情報・query/fragment/escaped path拒否は維持。任意外部homepageの自動fetch、独立サイトの収録は未実装。
- 公開repo一覧の通信/ページング失敗時は、取得・検証できた既存公開snapshotを時刻を変更せず再利用し、Hub本体の通常更新を継続。旧版も取得不能、または新規データの整合性・非公開混入エラーの場合は配信を中止して既存Pagesを保持。完全な公開repo一覧を観測した場合、既存公開catalog.jsonを検証済み旧版として読み、同じ公開repo/安定app ID/公開URL/出典の個別一時障害のみ過去の確認時刻のまま保持する。未確認の新規候補を掲載しない。repo削除・Pages停止・定義削除・HTTP 410は該当候補を除外。HTTP 404/redirect/通信障害は公開終了と断定しない。manifest証拠消失だけでも既知アプリを除外しない。旧版取得の障害は新規配信を中止。任意アイコン障害は局所化。3日値は鮮度の目安。
- 既存preview-pages workflowでmain変更・手動・日次03:17 UTCに検証済みJSONを生成し、preview/だけを既存Pagesへ配信。実公開取得はpreview-pagesに一元化し、catalog-contractは決定論的契約試験のみ（重複した公開API呼出を除去）。予定実行は同じ検証済みmainのためブラウザ再試験を省き、収集テストと生成は毎回実行。書込権限増加なし。失敗時は旧デプロイの有効期限を延長しない。
- クライアントは同一originのcatalog.jsonを起動時・再表示時（5分経過）に取得し、形状とURL/参照/時刻/重複を確認。成功版をlocalStorageに保管、取得失敗時は正常な最終版を使用し鮮度を明示。古いことのみで一覧や起動を止めない。新しい完全な一覧に無いappは再掲載しない。端末の古いキャッシュや既に開いた外部ページを強制回収する保証はない。
- 公開確認済みカタログ全アプリに共通の内部起動を適用し、固定4件の起動許可は撤廃。既存sandbox権限を変更せず、起動画面で外部起動/再読込を選択可能。実サイトの主要機能とiOS互換性は#3/#7で引き続き実証。
- 独立公開サイトの所有証拠・URL判定拡張、ETag/バックオフの最適化、公開repo副表示は同じsnapshotから生成。R4互換性は後続。
