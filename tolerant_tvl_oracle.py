# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
import json


class TolerantTVLOracle(gl.Contract):
    owner: Address
    tolerance_bps: u256
    seq: u256
    attestations: TreeMap[str, str]

    def __init__(self, tolerance_bps: int):
        self.owner = gl.message.sender_address
        self.tolerance_bps = u256(tolerance_bps)
        self.seq = u256(0)

    @gl.public.write
    def set_tolerance(self, tolerance_bps: int) -> None:
        if gl.message.sender_address != self.owner:
            raise Exception("only owner")
        if tolerance_bps <= 0 or tolerance_bps > 1000:
            raise Exception("tolerance must be 1..1000 bps")
        self.tolerance_bps = u256(tolerance_bps)

    @gl.public.write
    def attest_tvl(self, slug: str) -> None:
        url = "https://api.llama.fi/tvl/" + slug
        tol = int(self.tolerance_bps)

        def fetch_tvl() -> int:
            res = gl.nondet.web.get(url)
            return int(float(res.body.decode("utf-8").strip()))

        def leader_fn():
            return fetch_tvl()

        def validator_fn(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            theirs = leader_result.calldata
            try:
                mine = fetch_tvl()
            except Exception:
                return False
            if mine <= 0 or theirs <= 0:
                return False
            diff_bps = abs(mine - theirs) * 10000 // mine
            return diff_bps <= tol

        tvl = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

        self.seq = u256(int(self.seq) + 1)
        self.attestations[slug] = json.dumps({
            "tvl_usd": tvl,
            "tolerance_bps": tol,
            "seq": int(self.seq),
            "attester": str(gl.message.sender_address),
        })

    @gl.public.view
    def get_attestation(self, slug: str) -> str:
        return self.attestations.get(slug, "")

    @gl.public.view
    def meets_threshold(self, slug: str, min_tvl_usd: int) -> bool:
        raw = self.attestations.get(slug, "")
        if raw == "":
            return False
        return json.loads(raw)["tvl_usd"] >= min_tvl_usd
