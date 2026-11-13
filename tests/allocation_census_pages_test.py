"""Offline accounting cases; run remotely while local runtime testing is paused."""
import unittest
from allocation_census_pages import correlate_pages


def block(address,size,module='a.dll'):
    return dict(address=hex(address),requested_bytes=str(size),module=module)


class PageCorrelationTests(unittest.TestCase):
    scope=[dict(start='0x1000',end='0x3000')]

    def test_half_open_boundary_and_unobserved_pages(self):
        result=correlate_pages([block(0x1100,0xf00)],[0x1000,0x2000,0x4000],self.scope)
        self.assertEqual(result['observed_requested_bytes_on_private_pages'],0xf00)
        self.assertEqual(result['page_categories']['unobserved'],2)
        self.assertEqual(result['selected_scope_private_ws'],8192)
        self.assertEqual(result['outside_scope_private_ws'],4096)
        self.assertEqual(result['private_bytes_not_covered_by_observed_requests'],12288-0xf00)

    def test_cross_page_payload_and_nonresident_gap(self):
        result=correlate_pages([block(0x1ff0,0x2020)],[0x1000,0x4000],self.scope)
        self.assertEqual(result['observed_requested_bytes_on_private_pages'],32)
        self.assertEqual([p['observed_requested_bytes'] for p in result['observed_pages']],[16,16])

    def test_mixed_callers_do_not_double_count_page(self):
        result=correlate_pages([block(0x1100,100),block(0x1300,64,'b.dll')],
                               [0x1000],self.scope)
        self.assertEqual(result['private_ws'],4096)
        self.assertEqual(result['page_categories']['mixed_caller_modules'],1)
        self.assertEqual(result['observed_requested_bytes_on_private_pages'],164)
        self.assertEqual(result['observed_pages'][0]['uncovered_bytes'],3932)

    def test_zero_size_and_unknown_module(self):
        result=correlate_pages([block(0x1100,0),block(0x1200,32,None)],[0x1000],self.scope)
        self.assertEqual(result['page_categories']['unknown_caller_module'],1)
        self.assertEqual(result['observed_requested_bytes_on_private_pages'],32)

    def test_invalid_metadata_is_rejected(self):
        for entries in ([block(0x1100,512),block(0x1200,32)],
                        [block(0x1100,0),block(0x1100,0)],
                        [block(0x1100,-1)], [block(2**64-8,16)]):
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                correlate_pages(entries,[0x1000],self.scope)
        with self.assertRaises(ValueError):correlate_pages([],[0x1000,0x1000],self.scope)
        with self.assertRaises(ValueError):correlate_pages([],[0x1001],self.scope)


if __name__=='__main__':unittest.main()
