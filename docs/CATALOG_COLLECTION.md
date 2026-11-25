# R2 公開カタログ取得（収集・配信）

Owner #5。配信形状は docs/CATALOG_CONTRACT.md と schema v1。既存ホーム画面の外観を維持し、データ供給のみ接続する。

- 匿名公開 REST /users/kinoko34077/repos の所有repoのみ。Link全ページを devflow_mapped_read.github_pages.read_linked_rows へ委譲。10ページ×100件は現規模に対する安全予算であり、next残存は失敗。固定版の既存checkoutを CI で参照する（共通供給機構は既存Ownerの受入後に切替、Hub独自loaderなし）。
- 公開性・所有者・ID・重複を厳格に確認、最小フィールドへ投影。公開API応答自体が原子的ではない。非公開/不正行の混入や一覧途中障害は全体失敗、公開成果物を上書きしない。
- Pages有効の標準パスを候補とし、実HTTPと公開manifest（同じrepoパス内のstart_url、name/short_name、standalone/fullscreen/minimal-ui）で公開アプリの正の証拠を得る。単なるPages有効・HTTP 200だけでは自動収録しない。明示済みの例外は安定repo IDとkeyで登録し、実HTTPで確認。複数app、Pages外の既知Workerを扱う。Hub自身・archivedはアプリ対象外。repo一覧は公開確認済みのみ。
- 固定GitHub Pages originと所有repoパス、確認済みStandby Workerだけをアクセス対象とする。redirectを追わず、任意homepageや非HTTPS、資格情報、query、fragment、escaped path、別originのmanifest/iconをfetchしない。任意の外部独立サイト・custom domain・PWA以外の自動判定は後続。未確認は掲載しない。公開アプリの機能/埋込互換性とは別。
- 公開repo一覧の取得失敗は新規配信を中止し、既存Pagesを保持。完全な公開repo一覧を観測できた場合は、公開判定に失敗したアプリのみ非掲載とし、他の確認済みアプリと削除済みrepoの反映は進める。任意アイコン障害も局所化。3日有効期限は日次更新が2回失敗しても復旧機会を確保する暫定値。期限切れでは新規起動を止める。
- 既存preview-pages workflowでmain変更・手動・日次03:17 UTCに検証済みJSONを生成し、preview/だけを既存Pagesへ配信。予定実行は同じ検証済みmainのためブラウザ再試験を省き、収集テストと生成は毎回実行。書込権限増加なし。失敗時は旧デプロイの有効期限を延長しない。
- クライアントは同一originのcatalog.jsonを起動時・再表示時（5分経過）に取得し、形状とURL/参照/時刻/重複を確認。成功版をlocalStorageに保管、取得失敗時は有効な最終版のみ使用。期限切れでは公開アプリを非表示にしてfixtureを残す。新しい完全な一覧に無いappは再掲載しない。端末の古いキャッシュや既に開いた外部ページを強制回収する保証はない。
- 収集データは埋込権限ではない。既存試用4アプリに限り安定IDと完全一致URLで従来のopaque sandbox起動を維持。他はメニューから明示的外部起動。実機受入まで自動で埋込を許可しない。固定4件を一覧のデータ源として残さない。
- 非PWA/独立公開サイトの所有証拠・URL判定拡張、ETag/バックオフの最適化、公開repo副表示、R3残機能・R4互換性は後続。
