/* Generated literal kitty states; capture SHA-256 b00df940a8d246bfdc958ea46d67d8321d031d129b02db28cc2fe3b298a176a0.
 * Cursor movement and APC parsing belong to separate integration tests. */
static const Reference states[] = {
    {"replace-named-placement/place","a=T,f=24,i=1,s=20,v=20,p=7,C=1",1,1,20,20,0,0,1,1,{{0.0,0.0,20.000002,20.0,0.0,0.0,1.0,1.0},{0}}},
    {"replace-named-placement/move-same-placement","a=p,i=1,p=7,C=1",0,2,20,20,3,2,1,1,{{30.0,40.0,50.000001,60.0,0.0,0.0,1.0,1.0},{0}}},
    {"replace-named-placement/another-placement","a=p,i=1,p=8,C=1",0,2,20,20,6,4,1,2,{{30.0,40.0,50.000001,60.0,0.0,0.0,1.0,1.0},{60.0,80.0,80.000001,100.0,0.0,0.0,1.0,1.0}}},
    {"replace-named-placement/remove-first-placement","a=d,d=i,i=1,p=7",0,3,20,20,6,4,1,1,{{60.0,80.0,80.000001,100.0,0.0,0.0,1.0,1.0},{0}}},
    {"replace-named-placement/remove-final-and-data","a=d,d=I,i=1,p=8",0,3,20,20,6,4,0,0,{{0},{0}}},
    {"anonymous-placement-ids/place","a=T,f=24,i=1,s=20,v=20,C=1",1,1,20,20,0,0,1,1,{{0.0,0.0,20.000002,20.0,0.0,0.0,1.0,1.0},{0}}},
    {"anonymous-placement-ids/second-placement","a=p,i=1,C=1",0,2,20,20,3,2,1,2,{{0.0,0.0,20.000002,20.0,0.0,0.0,1.0,1.0},{30.0,40.0,50.000001,60.0,0.0,0.0,1.0,1.0}}},
    {"anonymous-placement-ids/remove-visible-keep-data","a=d,d=a",0,3,20,20,3,2,1,0,{{0},{0}}},
    {"anonymous-placement-ids/place-retained-data","a=p,i=1,C=1",0,2,20,20,3,2,1,1,{{30.0,40.0,50.000001,60.0,0.0,0.0,1.0,1.0},{0}}},
    {"inside-scroll-region/set-margins-and-place","a=T,f=24,i=1,s=10,v=40,C=1",1,1,10,40,0,1,1,1,{{0.0,20.0,10.000001,60.000005,0.0,0.0,1.0,1.0},{0}}},
    {"inside-scroll-region/scroll-one-row","",0,4,10,40,0,4,1,1,{{0.0,20.0,10.000001,40.000002,0.0,0.5,1.0,1.0},{0}}},
    {"inside-scroll-region/reverse-one-row","",0,5,10,40,0,1,1,1,{{0.0,40.0,10.000001,60.000002,0.0,0.5,1.0,1.0},{0}}},
    {"overlap-top-scroll-region/set-margins-and-place","a=T,f=24,i=1,s=10,v=40,C=1",1,1,10,40,0,0,1,1,{{0.0,0.0,10.000001,40.000005,0.0,0.0,1.0,1.0},{0}}},
    {"overlap-top-scroll-region/scroll-one-row","",0,4,10,40,0,4,1,1,{{0.0,0.0,10.000001,40.000005,0.0,0.0,1.0,1.0},{0}}},
    {"overlap-top-scroll-region/reverse-one-row","",0,5,10,40,0,1,1,1,{{0.0,0.0,10.000001,40.000005,0.0,0.0,1.0,1.0},{0}}},
    {"overlap-bottom-scroll-region/set-margins-and-place","a=T,f=24,i=1,s=10,v=60,C=1",1,1,10,60,0,3,1,1,{{0.0,60.0,10.000001,120.00001,0.0,0.0,1.0,1.0},{0}}},
    {"overlap-bottom-scroll-region/scroll-one-row","",0,4,10,60,0,4,1,1,{{0.0,60.0,10.000001,120.00001,0.0,0.0,1.0,1.0},{0}}},
    {"overlap-bottom-scroll-region/reverse-one-row","",0,5,10,60,0,1,1,1,{{0.0,60.0,10.000001,120.00001,0.0,0.0,1.0,1.0},{0}}},
};
