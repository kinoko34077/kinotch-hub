# R2 公開カタログ取得（初期slice）

Owner #5。配信形状は docs/CATALOG_CONTRACT.md と schema v1。既存UIを変更しない。

- 匿名公開 REST /users/kinoko34077/repos の所有repoのみ。Link全ページを devflow_mapped_read.github_pages.read_linked_rows へ委譲。10ページ×100件は現規模に対する安全予算であり、next残存は失敗。固定版の既存checkoutを CI で参照する（共通供給機構は既存Ownerの受入後に切替、Hub独自loaderなし）。
- 公開性・所有者・ID・重複を厳格に確認、最小フィールドへ投影。公開API応答自体が原子的ではない。非公開/不正行の混入や一覧途中障害は全体失敗、公開成果物を上書きしない。
- Pages有効の標準パスを候補とし、実HTTPと公開manifest（同じrepoパス内のstart_url、name/short_name、standalone/fullscreen/minimal-ui）で公開アプリの正の証拠を得る。単なるPages有効・HTTP 200だけでは自動収録しない。明示済みの例外は安定repo IDとkeyで登録し、実HTTPで確認。複数app、Pages外の既知Workerを扱う。Hub自身・archivedはアプリ対象外。repo一覧は公開確認済みのみ。
- 固定GitHub Pages originと所有repoパス、確認済みStandby Workerだけをアクセス対象とする。redirectを追わず、任意homepageや非HTTPS、資格情報、query、fragment、escaped path、別originのmanifest/iconをfetchしない。任意の外部独立サイト・custom domain・PWA以外の自動判定は後続。未確認は掲載しない。公開アプリの機能/埋込互換性とは別。
- 公開repo一覧・アプリ公開判定のtimeout/403/429/5xxは全体失敗。任意のアイコン取得障害はアイコンのみ省略し、アプリの公開判定を無効化しない。404/410/redirectは当該候補を非掲載。アイコンの不在は代替表示用に省略。3日暫定有効期限、shapeと参照/重複/URL/時刻を検証後atomic write。自動配信、last-good/鮮度表示、失効/削除伝播、ETag/再試行、UI接続は後続。CIはread-only、生成JSONはrunner内のみで、未受入の公開データはサイトへ反映しない。
