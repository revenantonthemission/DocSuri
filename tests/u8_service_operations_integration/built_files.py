"""The earlier units' files U8 keeps exactly as built, pinned by content (U8 plan Steps 22,
24 and 44; the person's decisions of 2026-10-24, "Move U8's lines out of U5", "Fix it in
U8", "Move, scope tools, test U2", and of 2026-10-25, "Start it at install, U8 snapshot").

Each digest is the SHA-256 of the file's bytes at the branch base, `origin/develop`
`bf82ed192af8144a56f69f8fc858e0a2685c7dbd` (U6's merge, pull request #54), from which
the U8 branch starts. A comparison against `HEAD` cannot guard these files: in CI the
checkout is the pull request's own commit, so `HEAD` already holds every change and the
diff is always empty. A pinned digest fails on any change, committed or not, in every
checkout, shallow ones included.

A file that must change later changes its pin in the same commit, where review sees it.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE_COMMIT = "bf82ed192af8144a56f69f8fc858e0a2685c7dbd"

BUILT_DIGESTS = {
    # U5's three restored files and U5's coverage scope (Step 22).
    "backend/u5_policy.py":
        "5bb52c4c198035f7de5c6e685c9a0fab8ce246670733dae0571b980a7f91246b",
    # Re-pinned 2026-10-31 (Build and Test, loop-back re-entry) to the bytes U5's
    # Build-and-Test loop-back 1 of 2026-10-28 left: the digest-adapter docstring moved
    # from the send_digest_email seam to digest_email.py. This pin lands with that
    # change in the same commit.
    "backend/modules/topics/delivery.py":
        "16680a8a6cd14d1c881544c1ff760066fe8494151e54c04157d9974e2def0095",
    "backend/u5_real_delivery.py":
        "a114e9332910317141d6e16a4066aa17cfbb84189c321e96d404d4a023ebd56b",
    # Re-pinned 2026-10-31 (Build and Test, loop-back re-entry) to the bytes U5's
    # Build-and-Test loop-back 1 of 2026-10-28 left: backend/local_observation.py joins
    # the include set (loop-back 1 decision L1-3). This pin lands with that change in
    # the same commit.
    "backend/.coveragerc.u5":
        "82719aa662846316da910756c97a255173b39ef00b8fa2e52dcec0f49b8182d5",
    # U4's policy, host and four research files, and U4's coverage scope (Step 22).
    "backend/u4_policy.py":
        "f344db6ba94f87f624a8e489a736b3668e04c4dae0046b80e761d324f98e2a91",
    "backend/u4_host.py":
        "c4c7e6bbf0f688f99be2a5b3a188553b1662dfa11cc65be1ea28966b30a2391a",
    "backend/modules/research/evidence.py":
        "b9f6ea37dce47de72cc8d037823eccf3dd54ac7f45db156fb98d17d43b66a399",
    "backend/modules/research/execution.py":
        "0619f90476cf65438ed4527993057b30648eac2f8e20b30655846a8ff4c1ae01",
    "backend/modules/research/jobs.py":
        "fd12c054d478077168781f4e742e96b913d3b51ddef55c3aebeca1315a6ac953",
    "backend/modules/research/service.py":
        "ad40c78fe1cf2dd473a251dd8c564835c1f888bc019f6674cb584c443059b8bc",
    "backend/.coveragerc.u4":
        "0555e635f43d6bf3a472b4a4658d7514a58253e63b22d82694fda75bef2a0bf9",
    # U3's coverage scope (Step 24).
    "backend/.coveragerc.u3":
        "ebddec3c02dc05a54672e89bcd938ed8abf444cff17297a1d3985f6fd1d6f665",
    # U2's key recovery, as built (Step 44).
    "backend/modules/accounts/control_key_recovery.py":
        "8d87d734788616a45f2cfff9aca75ca1da8a79d7aa4f68c3fbd93f186f883092",
    # U7's package files that end as built (Step 44; the person's decision of 2026-10-25,
    # "Move U8's code out of U7"): the ten U8 never changed, and `cli.py`, `enums.py` and
    # `profile.py`, restored to the branch base. The two seam files are in SEAM_DIGESTS.
    "ops/src/docsuri_ops/platform_control/__init__.py":
        "2f10d4d740180a5d0c8db1cb581ab329eece847117e484fb057403293424bd3b",
    "ops/src/docsuri_ops/platform_control/__main__.py":
        "fd686a582ff4c1f152c2932d79695d7314866e9c656db5430a450eded099d7c2",
    "ops/src/docsuri_ops/platform_control/authority.py":
        "1b0bbd0c4de35ddd42322892e85682def70eb2e66eb9885c8f7b81cbb939cd81",
    "ops/src/docsuri_ops/platform_control/cli.py":
        "cff2c395dda253ad9676b7ce1e742e6e8cffd116dd31bc2871cc1a836230b2c4",
    "ops/src/docsuri_ops/platform_control/enums.py":
        "0b4d3134644cac908828c98a25ff3b1f7dab3106d13341e17f3f103be59de0b7",
    "ops/src/docsuri_ops/platform_control/errors.py":
        "1815153a80500050fa53eb1763fac8aeecdbe9a25b8ff089ee09f4336a3864dc",
    "ops/src/docsuri_ops/platform_control/evidence.py":
        "d0760bdee9ce8741d154e44bc9f74dc7e4e2abd65030a006ae46e8b1d923832f",
    "ops/src/docsuri_ops/platform_control/inventory.py":
        "71650eedf38b4e9b1efc563aaa26b7752f3f035373eae42b52ac6137de3f0fa9",
    "ops/src/docsuri_ops/platform_control/observations.py":
        "3ea906c9b38979656b1d65e94239d1b9a4fee45d6158a4e2208ea40534318ab3",
    "ops/src/docsuri_ops/platform_control/profile.py":
        "8335b22b8623b0cf707a814834e2f1ffab634eb73559e521cb2470f0477642b6",
    "ops/src/docsuri_ops/platform_control/reconciler.py":
        "8ed3e67f97a8c28b605f1b6117bf4ec78daefdea67d532cb8b6f963bed537b3e",
    "ops/src/docsuri_ops/platform_control/schema.sql":
        "2ce334ec7b61879c7285e9afee4a91ebdbc238606cf0ed8baa9a7665dfb9e9df",
    "ops/src/docsuri_ops/platform_control/store.py":
        "de940f2fec41b8597f60f6e30de1780b0694d130183ee14f5a223955a44a9ff9",
    # U7's tool, bootstrap, supervisor, pytest ini and workflow (Step 44).
    # Re-pinned 2026-11-09 (Build and Test loop-back 1, Step 46(i)) under L1-77, the
    # person's answer of 2026-11-09 ("Both on Colima"): `clean_environment` also keeps
    # DOCKER_HOST when it is set. This reverses the person's decision of 2026-10-25 that
    # U7's tool does not change, for this one line only. This pin lands with that change
    # in the same commit.
    "scripts/verify_docsuri_u7.py":
        "ec1bd5d02bf535e3b8b8fa46efed92d516ed5abb51377e5d09513f2da78f73cb",
    "scripts/bootstrap_docsuri_u7.py":
        "80d6646d6f99ee2291d7ee8707a1d2ae81a944418dee95fabd163c03dcad4b14",
    "scripts/supervise_docsuri_u7.py":
        "9876d3f36a8dea84a5bbfffe3aef316353a7f2da625219f5941c860510f8da53",
    "backend/pytest.u7-platform-control.ini":
        "80218cd58c65dab891d10bd79824fe1a506e0046e0840ba26ad6264a98f79a25",
    ".github/workflows/u7-controlled-platform-protocols.yml":
        "350fc552b3287faf982de32ac17959f2902c1ba676a83e1c28a217741d082ff6",
    # U7's eighteen test files (Step 44).
    "tests/u7_controlled_platform_protocols/conftest.py":
        "fabff4567deb9ab0127e93f1d41e4fd0c622c038a93be9f244cdc7a6a0ba8a95",
    "tests/u7_controlled_platform_protocols/component/test_authority_logic.py":
        "85b15d968c5e4d2cdb1cec3b688d6172fa83d58dad5df35ac93290a828e8c609",
    "tests/u7_controlled_platform_protocols/component/test_cli_projection.py":
        "0a058f44136c480c0b5b21acde7cdd888649571f1ba035447dd009d59bc2e5e5",
    "tests/u7_controlled_platform_protocols/component/test_entrypoint.py":
        "592771b663c2204884086dba1f61e14689ad5d4deb04346402d143b26c0acfc5",
    "tests/u7_controlled_platform_protocols/component/test_executor.py":
        "363e796692f9c5262ed98e7b287273f4b169302ff3ef7c600368a615682b8456",
    "tests/u7_controlled_platform_protocols/component/test_inventory.py":
        "0e213a6375cd709bad2ffe74b4a3cf64a530853082b9b6305c58d2b8ce89b8b0",
    "tests/u7_controlled_platform_protocols/component/test_native_adapter.py":
        "fd74c2a66c67eee0cfbc047f38466953997a08418be658c8295e24bc83795dc1",
    "tests/u7_controlled_platform_protocols/component/test_state_projection.py":
        "9114fd365cf56657c4b38b484aee3918bccf98cc4a0cdbe756c9d189c3e9db13",
    "tests/u7_controlled_platform_protocols/database/test_guard_authority.py":
        "596b76ebaa1dc6b7092518492488c2ca19991a5e5d8d4844fc19476e0bb17d28",
    "tests/u7_controlled_platform_protocols/database/test_lease_and_binding.py":
        "2e3d677db72dc443af3c6eae13e6f7e7f0b56ac2a2d3ab5eda73eaf7a7e5267f",
    "tests/u7_controlled_platform_protocols/database/test_owner_privileges.py":
        "6e26eac7eb0f4da6e6f6a4c6cf32925f11465db2abd4839ffec3df9f93f04e4a",
    "tests/u7_controlled_platform_protocols/integration/test_cli_boundary.py":
        "12b8260c8bd557d7ed9729b2b247a128092af6d6e8e8c753561e122c8d4e6afa",
    "tests/u7_controlled_platform_protocols/integration/test_cli_in_process.py":
        "e32b6c8bab8a59abbb5054bdc58684a95739994abcd43b7ce37c00785d85abcb",
    "tests/u7_controlled_platform_protocols/operations/test_recovery.py":
        "1b61fed3ffddd43b4163f5fc6f49a84bbe7cdfc64751944d2696348283eb68e0",
    "tests/u7_controlled_platform_protocols/repository/test_crash_recovery.py":
        "7b35fa38a95372191c08bf15bd0e9473db7236afdfe0ec28101be425167f4880",
    "tests/u7_controlled_platform_protocols/repository/test_durability.py":
        "b127e16d4a950818407aa220faa0e1f67434d8b384dfe2dc98732c754c1d4ca9",
    "tests/u7_controlled_platform_protocols/repository/test_operation_lifecycle.py":
        "aae4e61feb1878e05beedd617321dd8ff7be5798ba0288c576c3bc3cff01f567",
    "tests/u7_controlled_platform_protocols/repository/test_reconciliation.py":
        "a9a9fd656d0a016e1840d66d1b5ca2866e4a7eec628313ac73495b1ac5681bf5",
    # U6's export history and copy, pinned 2026-11-10 (Build and Test loop-back 1, Step
    # 81(f)) at their bytes after the person's answers of 2026-11-02: the history offers
    # a fresh preview for an export invalidated before its write (L1-61, "Offer on
    # invalidated rows") and `authority-revoked` reads one text for both causes (L1-62,
    # "One text for both causes"). Neither file had a pin before.
    "frontend/src/u6-export/history.tsx":
        "374bd6b5445d98d27b44bfcdd62c139d570ae9dff20e48c890d4ec1261771a28",
    "frontend/src/u6-export/copy.ts":
        "521b184ebbd09cc34dca6b37120b16bce9b630edd592cc6920a7e860feaccf5c",
    # U6's history test, pinned 2026-11-10 (Step 82(f)) at its bytes after its two new
    # cases for L1-61 and L1-62 (Step 82(d)-(e)); re-pinned 2026-11-19 (U8 loop-back 3,
    # Step 155) at its bytes after U6's loop-back 3 Step 56(a) added its hostile
    # destination-title case (U6's L3-7, approved with U6's plan on 2026-11-18).
    "frontend/test/u6-export/history.test.tsx":
        "e8926a5b3c3fd463d2bb5432670b92410490ccb8ea3b9a49b332e457446638bc",
    # U1's shared ui.tsx and the shell's api.ts, pinned 2026-11-11 (Step 91(d)) under
    # L1-53, the person's answer of 2026-11-02: account mail refused up front while none
    # can be sent answers `account-mail.unavailable` with `MAIL_HELD_TEXT`, which moves to
    # api.ts. The bytes also hold L1-10's limit text, the seven-digit `Retry-After` read,
    # and ui.tsx's `ShellAnnounce` (Step 91(j), L1-9). Neither file had a pin before.
    "frontend/src/ui.tsx":
        "c5b0aed6a034089ed5b3b2570d93f77a5a1d12b55506ca8bc2032d5c8d4668a5",
    "frontend/src/api.ts":
        "0fd95c9406dbdb3649531af0dd3f052ea5883aa4cd814ef551b2b0b75abba56e",
    # U2's account controls, pinned 2026-11-11 (Step 91(m)) under L1-58, the person's
    # answer of 2026-11-02 ("Complete-app texts for both"). The bytes hold U8's two
    # changes in the file: the progress view's parts kept by policy (Step 17) and the
    # `isCompleteApp` switch, which only the complete assembly passes. The file had no pin
    # before, because U8 had already changed it.
    "frontend/src/account-controls.tsx":
        "9d75b5daa0be1b8a3d762379aca80d4f276a0bea6ea321566c77a4a5277e1cae",
    # The earlier units' lane configurations U8 reruns, pinned 2026-11-11 (Step 96(f)) at
    # their branch-base bytes, which have not changed since `bf82ed19`.
    "frontend/vitest.u2-account-controls.config.ts":
        "80b5eb9b814b5c2e2a44bbfd8d1d5307d117a341b007ee2157afb92ffd43a435",
    "frontend/vitest.u3-corpus.config.ts":
        "54330e7c22f0cc8a796a0186537e743b458351db85f8e717606e290a1153a3be",
    "frontend/vitest.u4-research.config.ts":
        "f8efda20dfaac90cf76b664ba86dd51bb7f5791da13a6d8bfb7b8b042f1bc528",
    "frontend/vitest.u5-topics.config.ts":
        "856a400fc49cf9219812ae3c1b1b2af224d8c91c98c733fcf497311c0ed826d0",
    "frontend/vitest.u6-export.config.ts":
        "9cb0a7ffd37ccabb4d26149be4652d0f8b51ee60f3018158af93bbec1fa21b6c",
    "backend/.coveragerc.u6":
        "428020cbccd2abb771b7b2397d194afc6b185a3b1b1698be1915e53f6d3eb17f",
    # U2's cumulative lane, pinned 2026-11-11 (Step 96(f)) at its current bytes: the
    # branch base plus U8's one include line, 'test/u8-complete/**/*.test.{ts,tsx}'.
    "frontend/vitest.u2-cumulative.config.ts":
        "5bc64960a173c95c5a30cdb7fedd815a10db9791ab770d2d6e784cd991b23adb",
}

# U1's 46 tracked test files, as `git ls-files tests/u1_integrated_paper_journey` lists
# them, conftests and fixtures included, pinned 2026-11-11 (Step 96(f), L1-33): 45 at their
# `bf82ed19` bytes, and `component/test_local_search.py` at its current bytes, by your
# decision of 2026-10-24, "Fix U1's test".
U1_TEST_DIGESTS = {
    f"tests/u1_integrated_paper_journey/{relative}": digest for relative, digest in {
        "component/test_account_entry.py":
            "b92029198e8feca6205cc3028c063963fc8406d0118c8e0c47066ed41c7d8c63",
        "component/test_account_key_custody.py":
            "2aec7df67af1dad2e85b38a058a6b5e550d6b833edc23a5bf0a2ecc79bd339d8",
        "component/test_admission_faults.py":
            "714a807b1dde27fb7a215713b71eff152fb1679f5d624468262685b69096141b",
        "component/test_assistance_requests.py":
            "be274307f8b3bda294fe60a80a73b39f82a8d4d8239ad555c548d8ad07116110",
        "component/test_canonical_worker.py":
            "3a51bdcf0ad7363fed207dfd4de098fc4d4283f326f908d01f7f21dc53f32dcd",
        "component/test_corpus_fixture_policy.py":
            "a12ff9009a62046fa6060a83f87a568c256f2392fc51e5fca113e936e2cf3fbe",
        "component/test_discovery_cursor_key.py":
            "1f9ab1bb532fbb05976ba1afba3622a3623de661bb0ecfe048dc3c2f56549ffe",
        "component/test_execution_payload.py":
            "5c5d001f5ce98b8c1d382c884f9468cfd566e4bb4ebcc5fc367262c18fff26f3",
        "component/test_fixture_history.py":
            "7488692d218056f62cd0c74415778c2dd9ec3e8252b90df4c42552951b11bd29",
        "component/test_fixture_lock.py":
            "a082adf6bed7dd319efe7c598c5a5768cfa9cff275d6a76f3a76c45c8f3057f7",
        "component/test_library_context.py":
            "305cfc4866f7f8e5724f5db191c78e2db9c557c03beb5ae40dc0be0ed2106ae7",
        "component/test_local_host.py":
            "dadcaa5d576d3c759140dcc35dcdb379fe061e171dd315833326fb562e1770a1",
        "component/test_local_models.py":
            "40f6dd600b9e1c1abe5ac7da48559dc2adeb346a0ecf130bc31b3bddf183808f",
        "component/test_local_observation.py":
            "4362f9cc15948583a753c9e75e5b7af13c19e7ecb5ed17ba496a2ad47156ce0d",
        # At its current bytes: your decision of 2026-10-24, "Fix U1's test".
        "component/test_local_search.py":
            "e0432cf92997611ec22ca5efa0e71f1982a2d45957de026c7811fbca8d53bff4",
        "component/test_local_transport.py":
            "553205299b8d9c61a72e585b11b126ed8a20b5a10b8714990feb30d863043343",
        "component/test_paper_fixture_manifest.py":
            "1c3a7d2da6b039648edaa41fabec0cc7b225f91051fdc83640cbd9fd7f01b9ff",
        "component/test_personal_defaults.py":
            "814975678a88e8c2256c890461e57a27de7a8d5f0554822894d4d58dfe4c42c9",
        "component/test_preauthentication.py":
            "fa58961ae0549d0e1038557017df5fa82a158f91e6ec3bb8b2efeb9d4e4891b5",
        "component/test_private_records.py":
            "fd7e4b88a28d32af75e7043db7538e20e7e4b64e7475c10f1f74f39b30e4cd1c",
        "component/test_publication_budget.py":
            "495c2931490bd55ada871d501a64c3df87cce60a2a0debd47296a7d45131031f",
        "component/test_runner.py":
            "028cc6f9116ff580860bc85f27d1eb84f113d7ff1f6190c1d9073d59b5340b68",
        "component/test_source_parser.py":
            "30e8bbcbf14c2a0f7a339b9d0b2345ec28a205943a548efbc335f98552f1e6b0",
        "component/test_worker.py":
            "fb9fe81f4ec49282b8193b08681d7b6de8d13c025986cbedac65c02aa3f3e2ed",
        "conftest.py":
            "097875744bae6cb2ba10277d377068a748dae3fe3cafe311a8f18d7363fc9a0a",
        "database/test_durable_state.py":
            "63ad6815b197ba50b420d0879d68e3fc575a64f26b7a3f4797d6345469f59acc",
        "database/test_owner_authority.py":
            "279a1e9539e06ca71e4ff911c032fc1ffae4087431a3ce8da4b55cd6c434ec32",
        "fixtures/history.py":
            "333637da6c19aca284a0611ee62eb1a633e4bef76f66e77362ed2727c0d1a8be",
        "fixtures/paper-metadata.json":
            "bf4c29f8bb053580ee5f78c7779af108253fc8ab8bb243d6fce7d94778a24bc3",
        "fixtures/research-queries.json":
            "940a7f45ae1383d28fa03f695bb86b993915aeb55dae034dbc705cf2ec6b658e",
        "integration/test_account_http.py":
            "3a5887ef7629c4dc75f94e072ab042b262cd2620de73835ace3b9017c6a7ae81",
        "integration/test_journey_http.py":
            "9660ba351a1d8788b856882cdc9d9db363bd4cb06cc4f29270912639e213daec",
        "model/test_source_outputs.py":
            "d8ab40ef0df58d4fa77b0199cdad06aeff90c7c6f5f0c610dd183b3b4dd045cf",
        "operations/test_operations_recovery.py":
            "38f71414bff23f18f2747632bee7d9a25ceb63f756d0f1cd2e46d2fb27fae29c",
        "repository/conftest.py":
            "28983d2894adabfe86dff1e9e1a7b149124a24241624cfc4feaffeb785cd6a2c",
        "repository/test_admission_coordinator.py":
            "5e8b28204fb9669b0fae406cb22ffe248a8ae4669a5cb058372ad629df100b7d",
        "repository/test_canonical_payload_boundary.py":
            "b2ae9ede31456967ba19a1163608b050eadf449ebe78341e089f35742306f737",
        "repository/test_corpus_and_recovery.py":
            "8a00d47bed563887513b638bd7be6e9cc243baec7158bb0772f6d6061de466c2",
        "repository/test_database_realms.py":
            "ede481f6fca878da7d59f3bc4a36bd1b100345b64fd64fa0740742178e28b8f2",
        "repository/test_execution_claims.py":
            "4a0ae58f903e37918df04e8a48685616f79a7714435d62ad0aab70fb27c11afa",
        "repository/test_execution_recovery.py":
            "a3db54f5c6a7435d4c100daf228277f896fffb6d184b729ad941c64f744deeb5",
        "repository/test_library_references.py":
            "c8522d23f68b3290f855113d03c04a9b4310881e52d51152aad4a3e18f669a15",
        "repository/test_persistence.py":
            "db07109148a4348fb40573dfe6de6b621b0dcbb6f0496b5b74e9bffeec68e2fe",
        "repository/test_research_queries.py":
            "cf19ced3d9dd5d6618ae8120707be3e822f981917427b9771062cd1ba547be98",
        "repository/test_typed_requests.py":
            "461f7c8a9cab74f23f28ed267467712f4b9876b94888653f1fd6152ca36186e4",
        "repository/test_worker.py":
            "153c1918089588560eb76c9d145df83387e3b307aa8ae4b5bde994caa22a8383",
    }.items()
}

# U7's two seam files, pinned at their digests after the seam (Step 44): the branch-base
# text plus `executor.run_effect`'s `adapter_module` and `native_adapter.main`'s `effect`,
# each defaulting to U7's built behaviour, and one name more in `run_effect`'s child
# environment, DOCKER_HOST (L1-78). Any further edit changes its pin here.
SEAM_DIGESTS = {
    # Re-pinned 2026-11-09 (Build and Test loop-back 1, Step 46(h)) under L1-78, the
    # person's answer of 2026-11-09 ("U7 executor keeps it"): `run_effect` hands its
    # bounded child DOCKER_HOST when the caller's environment holds it. This pin lands
    # with that change in the same commit.
    "ops/src/docsuri_ops/platform_control/executor.py":
        "1146454745149c774ab970c1ab61cdb9939923b156a58b2dc80348f22df38f2f",
    "ops/src/docsuri_ops/platform_control/native_adapter.py":
        "1a87c94e9c4b937fd7838a7b7dbc2e95a9d2930e10193f5416168f294d34f5a0",
}


def digest_of(path: Path) -> str | None:
    """The SHA-256 of a file's bytes, or None when it is missing."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError:
        return None


def changed_from_built(paths: Iterable[str], *, root: Path = ROOT,
                       pins: dict[str, str] = BUILT_DIGESTS) -> dict[str, str | None]:
    """Each named file whose bytes differ from its pin, with the digest found (None when
    the file is missing). A path without a pin is a test error, never a pass."""
    found = {}
    for relative in paths:
        if relative not in pins:
            raise KeyError(f"no pinned digest for {relative}")
        actual = digest_of(root / relative)
        if actual != pins[relative]:
            found[relative] = actual
    return found
