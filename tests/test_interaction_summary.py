"""A group exit code alone cannot certify all requested cases on one image."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import summarize_interaction as report


class ReportTest(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        old=Path.cwd(); os.chdir(tmp.name); self.addCleanup(os.chdir,old)
        config=patch.dict(os.environ,dict(INDEPENDENT='["input","bell"]',SHELL_BACKED='[]',
            INDEPENDENT_STATUS='success',SHELL_STATUS='skipped',PRODUCT_COMMIT='a'*40,PRODUCT_RUN='1',
            GITHUB_SHA='b'*40,GITHUB_RUN_ID='2',GITHUB_RUN_ATTEMPT='1',GITHUB_STEP_SUMMARY='summary.md'))
        config.start(); self.addCleanup(config.stop)
        for group in ('input','bell'): self.group(group,'c'*64)

    def group(self,group,sha):
        base=Path('build/group-receipts')/f'interaction-receipt-{group}-2-1'
        def save(key,value):
            path=base/key;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value))
        save('interaction-product/SOURCE-HOST.json',dict(SourceCommit='a'*40,Executable=dict(SHA256=sha,Bytes=42)))
        save('interaction/identity.json',dict(fixture_commit='b'*40,executable_sha256=sha,executable_bytes=42))
        rows=[dict(id=x['id'],status='passed',exit_code=0,cleanup=dict(terminated_remaining=False,
              after=dict(active=0),remaining_processes=[])) for x in report.catalog() if x['group']==group]
        save('interaction/results.json',rows)
        return base/'interaction/results.json'

    def inspect(self):
        with contextlib.redirect_stdout(io.StringIO()): status=report.main()
        return status,json.loads(Path('build/interaction-report.json').read_text())

    def test_green_selected_groups_do_not_claim_full_regression(self):
        status,result=self.inspect();self.assertEqual(status,0)
        self.assertEqual(result['scope'],'selected groups only');self.assertEqual(result['verified'],result['expected'])

    def test_internally_consistent_groups_on_different_images_cannot_be_combined(self):
        self.group('bell','d'*64);status,result=self.inspect()
        self.assertNotEqual(status,0);self.assertEqual(len(result['images']),2)

    def test_duplicate_cannot_substitute_for_missing_case(self):
        p=self.group('bell','c'*64);rows=json.loads(p.read_text());rows[1]=rows[0];p.write_text(json.dumps(rows))
        status,result=self.inspect();self.assertNotEqual(status,0);self.assertLess(result['verified'],result['expected'])

    def test_manual_paste_cannot_certify_automatic_right_click_or_vice_versa(self):
        drag=[[16,True],['left',True],['left',False],[16,False]]
        click=[['right',True],['right',False]]
        paste=[[17,True],[16,True],[86,True],[86,False],[16,False],[17,False]]
        enter=[[13,True],[13,False]]
        for manual,keys in ((True,paste),(False,[])):
            report.verify_right_gesture(drag+click+keys+enter,manual)
            with self.assertRaises(ValueError):
                report.verify_right_gesture(drag+click+keys+enter, not manual)
            for invalid in (drag[:-1]+click+drag[-1:]+keys+enter, drag+click+click+keys+enter):
                with self.assertRaises(ValueError):
                    report.verify_right_gesture(invalid, manual)

    def test_image_in_title_or_retry_does_not_prove_a_chat_attachment(self):
        client='opencode'; binding='ctrl-shift-v'
        image=dict(generated_pixels_match=True, png_size=[32,16], mime='image/png', sha256='c'*64)
        def request(title, *images):
            return dict(path='/v1/chat/completions',text=['NEMOTERM_OPENCODE_IMAGE_CTRL_SHIFT_V'],
                        has_opencode_title_instruction=title,images=list(images))
        title=request(True,image); chat=request(False,image); empty=request(False)
        for valid in ([title,chat],[chat,title],[title,chat,empty]):
            self.assertEqual(report.chat_attachment(valid,client,binding)['title_images'],1)
        for bad in ([title],[title,empty],[empty,title,chat],[chat,chat],[request(False,image,image)],
                    [request(False,dict(image,generated_pixels_match=False))], [dict(chat,text=['OTHER'])]):
            with self.subTest(bad=bad),self.assertRaises(ValueError):report.chat_attachment(bad,client,binding)

    def test_forced_cleanup_cannot_pass_even_with_exit_zero(self):
        p=self.group('bell','c'*64);rows=json.loads(p.read_text());rows[0]['cleanup']['terminated_remaining']=True
        p.write_text(json.dumps(rows));status,result=self.inspect();self.assertNotEqual(status,0)
        self.assertFalse(result['groups']['bell']['cases'][rows[0]['id']]['verified'])


if __name__=='__main__': unittest.main()
