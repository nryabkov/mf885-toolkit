/* v6: stock channel12 startup repair plus NULL-safe parser observation. */
#include "native.h"
#include "message.h"
#include "lifecycle.h"
#include "legacy_bindings.h"
#include <stddef.h>
#define ENTER ((uint32_t (*)(void))(uintptr_t)0x06426160u)
#define LEAVE ((void (*)(uint32_t))(uintptr_t)0x06426178u)
#define LEGACY_POST ((int32_t (*)(uint32_t,void *))(uintptr_t)CC_LEGACY_POST)
#define LEGACY_READ ((int32_t (*)(uint32_t,void *))(uintptr_t)CC_LEGACY_READ)
#define TRACK ((uint32_t (*)(uint32_t,uint32_t,uint32_t))(uintptr_t)CC_LEGACY_TRACK)
#define NEW_BUFFER ((void *(*)(uint32_t))(uintptr_t)CC_LEGACY_BUFFER)
#define DISCARD ((int32_t (*)(void **))(uintptr_t)CC_LEGACY_DISCARD)
#define LOOKUP ((void *(*)(void *,const char *))(uintptr_t)0x064349efu)
#define TEXT ((char **(*)(void *))(uintptr_t)0x06434e9fu)
#define DESTROY ((void (*)(void *))(uintptr_t)0x06433ee5u)
#define SLOT12 (*(void *volatile *)(uintptr_t)(0x06987048u+12u*4u))
#define SNAPSHOT_BYTES (36u+CC_OUTPUT_MAX)
#define WIRE_BYTES (4u+2u*SNAPSHOT_BYTES)
extern int32_t cc_original_parser(void *,const char *,uint32_t);
extern int32_t cc_original_response(uint32_t,uint32_t,uint32_t,const char *);
static uo_port_arena *arena(void) {
    uo_port_arena *a=*(uo_port_arena *volatile *)(uintptr_t)0x0694aa5cu;
    return a && a!=(void *)(uintptr_t)0x06e9db18u && a->magic==0x554f5031u ? a : 0;
}
static uint32_t task(uint32_t saved) {
    if ((saved&0xdfu)!=0x13u || *(volatile uint16_t *)(uintptr_t)0x0694a1a2u) return 0;
    return *(volatile uint32_t *)(uintptr_t)0x0695e0dcu;
}
int32_t cc_output(const char *,void *);
static void finish(uo_port_arena *a,uint32_t phase,int32_t status) {
    cc_state *c=&a->console;
    if(c->original_output && c->parser) {
        void **slot=(void **)((uintptr_t)c->parser+0x528u);
        if(*slot==(void *)cc_output)*slot=(void *)(uintptr_t)c->original_output;
        c->original_output=0;
    }
    a->console.phase=phase;
    a->submission.status=status;
    if (phase==CC_UNKNOWN) a->console.quarantined=1;
}
static int active(const cc_state *c) {
    return c->phase==CC_RUNNING || c->phase==CC_PENDING;
}
static int same(const char *a,const char *b,uint32_t n) {
    while(n--) if(*a++!=*b++) return 0;
    return 1;
}
static int equal_text(const char *a,const char *b) {
    if(!a)return 0;
    while(*b) {if(*a++!=*b++)return 0;}
    return !*a;
}
static int begins_text(const char *a,const char *b) {
    if(!a)return 0;
    while(*b)if(*a++!=*b++)return 0;
    return 1;
}
static void append(cc_state *c,const char *text) {
    if(!text)return;
    for(uint32_t i=0;i<4096u;++i) {
        char ch=text[i];
        if(!ch)return;
        if(c->output_count<CC_OUTPUT_MAX)c->output[c->output_count++]=ch;
        else {c->truncated=1;return;}
    }
    c->truncated=1;
}
/* Explicit freestanding zero primitive; no implicit host/ARMv7 runtime. */
void __aeabi_memclr4(void *pointer,uint32_t bytes) {
    volatile uint8_t *p=pointer;while(bytes--)*p++=0;
}
static int valid_node(uintptr_t p,uintptr_t node) {
    for(uint32_t i=0;i<8u;++i)if(node==p+0x590u+28u*i)return 1;
    return 0;
}
static void count_event(uint32_t *value) {if(*value!=UINT32_MAX)++*value;}
/* Called only inside a real parser invocation: its object/text are borrowed,
 * never retained or looked up later from an HTTP read. No command parameters,
 * response text, external pointer dereferences, callback changes or timers. */
static void diagnose(cc_state *c,void *parser,const char *text,uint32_t bytes,int own,uint32_t caller) {
    cc_diagnostic *d=&c->diagnostic;uintptr_t p=(uintptr_t)parser;
    count_event(&d->samples);count_event(own?&d->owned_calls:&d->foreign_calls);
    d->flags=3;d->pending_count=d->pending_mask=0;
    for(uint32_t i=0;i<8u;++i)d->pending_tags[i]=0;
    d->parser_address=(uint32_t)p;d->caller_address=caller;
    d->callback_address=d->pending_address=d->callback_class=0;
    if(!parser) {d->flags=1;return;} /* Sampled, no readable parser object. */
    uint32_t output=*(uint32_t *)(p+0x528u);
    d->parser_address=(uint32_t)p;d->callback_address=output;d->caller_address=caller;
    d->callback_class=output==0x060957c1u?1u:output==(uintptr_t)cc_output?2u:0u;
    if(!own) {
        for(uint32_t i=0;i<24u;++i)d->foreign_verb[i]=0;
        if(text && bytes>=2u && text[0]=='A' && text[1]=='T')
            for(uint32_t i=0;i<bytes && i<23u;++i) {
                char ch=text[i];
                if(!((ch>='A'&&ch<='Z') || (ch>='a'&&ch<='z') || ch=='+'))break;
                d->foreign_verb[i]=ch;
            }
    }
    uintptr_t node=*(uint32_t *)(p+0x584u);
    d->pending_address=(uint32_t)node;
    while(node) {
        uint32_t index=0;
        while(index<8u && node!=p+0x590u+28u*index)++index;
        if(index==8u){d->flags=(d->flags&~2u)|16u;break;}
        uint32_t bit=1u<<index;
        if(d->pending_mask&bit){d->flags=(d->flags&~2u)|4u;break;}
        uint32_t *n=(uint32_t *)node;
        if(n[1]!=p){d->flags=(d->flags&~2u)|8u;break;}
        d->pending_mask|=bit;d->pending_tags[d->pending_count++]=n[2];node=n[0];
    }
}
/* Caller holds IRQ guard. Follow only the eight in-object pending records. */
static int pending(void *parser,uint32_t tag) {
    if(!parser)return 0;
    uintptr_t p=(uintptr_t)parser;
    uint32_t *node=*(uint32_t **)(p+0x584u);
    for(uint32_t i=0;node && i<8u;++i) {
        uintptr_t n=(uintptr_t)node;
        if(!valid_node(p,n) || node[1]!=p)return 0;
        if(node[2]==tag)return 1;
        node=(uint32_t *)(uintptr_t)node[0];
    }
    return 0;
}
static int take_tag(uo_port_arena *a,uint32_t tag) {
    cc_state *c=&a->console;
    if((tag>>16)!=12u || !pending((void *)(uintptr_t)c->parser,tag))return 0;
    if(c->tag)return c->tag==tag;
    if((tag&0xffffu)<=c->last_tag) {finish(a,CC_UNKNOWN,-2017);return 0;}
    c->tag=tag;c->last_tag=tag&0xffffu;return 1;
}
int32_t cc_output(const char *text,void *userdata) {
    uint32_t saved=ENTER();uo_port_arena *a=arena();
    if(a && active(&a->console) && a->console.kind==CC_AT && a->console.parser) {
        cc_state *c=&a->console;
        void *expected=*(void **)((uintptr_t)c->parser+0x534u);
        if(userdata==expected) {
            append(c,text);
            if(text && equal_text(text,"\r\nOK\r\n"))finish(a,CC_SUCCESS,0);
            else if(text && (equal_text(text,"\r\nERROR\r\n") || begins_text(text,"\r\n+CME ERROR:") || begins_text(text,"\r\n+CMS ERROR:")))finish(a,CC_ERROR,-2002);
        }
    }
    LEAVE(saved);return 0;
}
int32_t cc_response(uint32_t tag,uint32_t code,uint32_t error,const char *text) {
    uint32_t saved=ENTER();uo_port_arena *a=arena();
    if(a && (tag>>16)==12u) {
        cc_diagnostic *d=&a->console.diagnostic;count_event(&d->responses);
        d->last_response_tag=tag;d->last_response_code=code;d->last_response_error=error;
    }
    if(a && active(&a->console) && a->console.kind==CC_AT && take_tag(a,tag)) {
        if(text){append(&a->console,text);append(&a->console,"\r\n");}
    }
    LEAVE(saved);
    return cc_original_response(tag,code,error,text);
}
void cc_worker_release(void *pointer) {
    uintptr_t caller=(uintptr_t)__builtin_return_address(0);
    uint32_t saved=ENTER();uo_port_arena *a=arena();
    if(a && a->console.phase==CC_QUEUED && a->console.queued_pointer==(uintptr_t)pointer) {
        cc_state *c=&a->console;c->queued_pointer=0;
        if(caller==0x060956cfu) {
            if(task(saved)) {c->worker_task=task(saved);c->phase=CC_READY;}
            else finish(a,CC_UNKNOWN,-2010);
        }
        else if(caller==0x06095693u)finish(a,CC_ERROR,-2004);
        else finish(a,CC_UNKNOWN,-2011);
    }
    LEAVE(saved);
    ((void (*)(void *))(uintptr_t)0x0644f00fu)(pointer);
}
int32_t cc_parser(void *parser,const char *text,uint32_t bytes,uint32_t caller) {
    uint32_t saved=ENTER();uo_port_arena *a=arena();int owned=0;
    int ours=a && a->console.phase==CC_READY && parser==SLOT12 && task(saved)==a->console.worker_task;
    if(a && parser==SLOT12)diagnose(&a->console,parser,text,bytes,ours,caller);
    if(ours) {
        cc_state *c=&a->console;
        int32_t reason=0;
        if(!parser)reason=-2021;
        else if(bytes!=c->count+1u)reason=-2012;
        else if(!same(text,c->command,c->count))reason=-2013;
        else if(text[c->count]!='\r')reason=-2014;
        else if(*(uint32_t *)((uintptr_t)parser+0x584u)){reason=-2015;count_event(&c->diagnostic.busy_rejections);}
        if(!reason) {c->parser=(uintptr_t)parser;c->phase=CC_RUNNING;owned=1;}
        else {
            /* Busy before ownership is a known rejection: original parser was
             * never called for this command and its callback was not replaced.
             * Keep the foreign pending work untouched. The consumed sequence
             * is not replayable; a later explicit command needs a new sequence.
             * Every ambiguous ownership/integrity failure still quarantines. */
            finish(a,(reason==-2015 || reason==-2021)?CC_ERROR:CC_UNKNOWN,reason);owned=-1;
        }
    }
    LEAVE(saved);
    if(!owned) {
        saved=ENTER();a=arena();
        if(a && active(&a->console) && a->console.parser==(uintptr_t)parser)
            finish(a,CC_UNKNOWN,-2016); /* A foreign parser producer invalidates the lease. */
        LEAVE(saved);
        return cc_original_parser(parser,text,bytes);
    }
    if(owned<0)return -1;
    cc_state *c=&a->console;int32_t result;
    if(c->kind==CC_USSD) {
        /* Worker owns this copied buffer; replace its CR with an explicit NUL. */
        ((char *)text)[c->count]=0;
        result=-2005;
        if(TRACK(UO_TRACK_HTTP_BEGIN,c->sequence,0)) {
            result=((int32_t (*)(uint32_t,uint32_t,const char *,uint32_t))(uintptr_t)0x066e1485u)(0,4,text,c->count);
            TRACK(UO_TRACK_HTTP_FINISH,(uint32_t)result,0);
        }
        saved=ENTER();finish(a,result?CC_ERROR:CC_SUCCESS,result);LEAVE(saved);
        return result;
    }
    c->original_output=*(uint32_t *)((uintptr_t)parser+0x528u);
    result=((int32_t (*)(void *,uint32_t,void *))(uintptr_t)0x0658a57bu)(parser,7,(void *)cc_output);
    if(result) {saved=ENTER();finish(a,CC_ERROR,result);LEAVE(saved);return result;}
    result=cc_original_parser(parser,text,bytes);
    saved=ENTER();
    if(c->phase==CC_RUNNING) {
        uint32_t *node=*(uint32_t **)((uintptr_t)parser+0x584u);
        if(result)finish(a,CC_ERROR,result);
        else if(node) {
            uintptr_t n=(uintptr_t)node,p=(uintptr_t)parser;
            if(!valid_node(p,n))finish(a,CC_UNKNOWN,-2018);
            else if(take_tag(a,node[2]))c->phase=CC_PENDING;
            else if(c->phase!=CC_UNKNOWN)finish(a,CC_UNKNOWN,-2019);
        } else finish(a,CC_UNKNOWN,-2020);
    }
    LEAVE(saved);return result;
}
static void *tree(uint32_t phase,void *context,uint32_t expected) {
    if(phase!=expected || !context || *(uint16_t *)context!=1u)return 0;
    return *(void **)((uint8_t *)context+12u);
}
static int command_valid(const cc_request *r) {
    for(uint32_t i=0;i<r->count;++i) {
        uint8_t c=r->command[i];
        if(r->kind==CC_AT && c==';')return 0; /* One command, no batches. */
        /* This initial SS adapter uses selector4 without alphabet conversion.
         * Accept only bytes whose printable ASCII and GSM default values agree. */
        if(r->kind==CC_USSD && (c=='$'||c=='@'||(c>=91u&&c<=96u)||c>=123u))return 0;
    }
    return 1;
}
int32_t cc_http_post(uint32_t phase,void *context) {
    void *t=tree(phase,context,3);void *node=t?LOOKUP(t,"console_v1"):0;
    if(!node) {
        /* Existing reads stay compatible. Once this session has used the new
         * API, old fixed-code writes cannot move its sequence behind its back. */
        uint32_t guard=ENTER();uo_port_arena *current=arena();
        int used=current && current->console.sequence;
        LEAVE(guard);
        return used?0:LEGACY_POST(phase,context);
    }
    if(*(uint32_t *)((uint8_t *)t+4u)!=1u)return 0;
    cc_request request;char **slot=TEXT(node);
    int valid=slot && *slot && cc_parse_request(*slot,&request) && command_valid(&request);
    DESTROY(node);*(uint32_t *)((uint8_t *)t+4u)=0;
    if(!valid)return 0;
    uint32_t saved=ENTER();uo_port_arena *a=arena();int reserved=0;
    if(a && task(saved)) {
        uo_submission *s=&a->submission;cc_state *c=&a->console;
        if(request.kind==CC_CLAIM) {
            if(!(s->nonce_low|s->nonce_high|s->sequence|(uint32_t)s->status)) {
                s->nonce_low=request.nonce_low;s->nonce_high=request.nonce_high;
            }
        } else if(!c->quarantined && s->nonce_low==request.nonce_low && s->nonce_high==request.nonce_high &&
            (s->nonce_low|s->nonce_high) && s->sequence!=UINT32_MAX && request.sequence==s->sequence+1u && s->status!=INT32_MIN) {
            s->sequence=request.sequence;s->status=INT32_MIN;
            c->phase=CC_QUEUED;c->sequence=request.sequence;c->kind=request.kind;c->count=request.count;
            c->queued_pointer=c->worker_task=c->tag=c->output_count=c->truncated=0;
            for(uint32_t i=0;i<=request.count;++i)c->command[i]=request.command[i];
            reserved=1;
        }
    }
    LEAVE(saved);
    if(!reserved)return 0;
    void *data=NEW_BUFFER(request.count+2u);int32_t status=-2006;
    if(data) {
        for(uint32_t i=0;i<request.count;++i)((char *)data)[i]=request.command[i];
        ((char *)data)[request.count]='\r';((char *)data)[request.count+1u]=0;
        saved=ENTER();a->console.queued_pointer=(uintptr_t)data;LEAVE(saved);
        uint32_t message[4]={12u,request.count+1u,(uintptr_t)data,0};
        uint32_t handle=*(volatile uint32_t *)(uintptr_t)0x06940cb4u;
        status=handle?((int32_t (*)(uint32_t,uint32_t,const void *,uint32_t))(uintptr_t)0x0640e204u)(handle,12,message,0):-2007;
        if(status)DISCARD(&data); /* Successful send transferred ownership. */
    }
    if(status) {
        saved=ENTER();
        if(a->console.phase==CC_QUEUED && a->console.sequence==request.sequence) {
            a->console.queued_pointer=0;finish(a,CC_ERROR,status);
        }
        LEAVE(saved);
    }
    return 0;
}
static int read_diagnostic(void *t) {
    void *node=LOOKUP(t,"queue_v1");if(!node)return 0;
    char **slot=TEXT(node);if(!slot)return -1;
    enum { BYTES=sizeof(cc_diagnostic), WIRE=4+BYTES*2 };
    char *out=NEW_BUFFER(WIRE);if(!out)return -1;
    uint8_t copy[BYTES];uint32_t saved=ENTER();uo_port_arena *a=arena();
    for(uint32_t i=0;i<BYTES;++i)copy[i]=a?((uint8_t *)&a->console.diagnostic)[i]:0;
    LEAVE(saved);
    const char *hex="0123456789abcdef";out[0]='q';out[1]='2';out[2]=':';
    for(uint32_t i=0;i<BYTES;++i){out[3+2*i]=hex[copy[i]>>4];out[4+2*i]=hex[copy[i]&15u];}
    out[WIRE-1]=0;void *old=*slot;*slot=out;DISCARD(&old);return 0;
}
int32_t cc_http_read(uint32_t phase,void *context) {
    void *t=tree(phase,context,4);void *node=t?LOOKUP(t,"console_v1"):0;
    if(!node)return LEGACY_READ(phase,context);
    if(read_diagnostic(t))return -1;
    char **slot=TEXT(node);if(!slot)return -1;
    char *old=*slot;if(old)old[0]=0;
    char *out=NEW_BUFFER(WIRE_BYTES);if(!out)return -1;
    uint32_t header[9]={0};uint8_t snapshot[SNAPSHOT_BYTES];
    uint32_t saved=ENTER();uo_port_arena *a=arena();
    if(a) {
        cc_state *c=&a->console;
        header[0]=a->submission.nonce_low;header[1]=a->submission.nonce_high;
        header[2]=a->submission.sequence;header[3]=c->phase;header[4]=c->kind;
        header[5]=(uint32_t)a->submission.status;header[6]=c->tag;
        header[7]=c->output_count;header[8]=c->truncated|c->quarantined<<1;
    }
    for(uint32_t i=0;i<36u;++i)snapshot[i]=((uint8_t *)header)[i];
    for(uint32_t i=0;i<CC_OUTPUT_MAX;++i)snapshot[36u+i]=a && i<a->console.output_count?(uint8_t)a->console.output[i]:0;
    LEAVE(saved);
    const char *hex="0123456789abcdef";out[0]='c';out[1]='1';out[2]=':';
    for(uint32_t i=0;i<SNAPSHOT_BYTES;++i){out[3u+2u*i]=hex[snapshot[i]>>4];out[4u+2u*i]=hex[snapshot[i]&15u];}
    out[WIRE_BYTES-1u]=0;*slot=out;void *owned=old;DISCARD(&owned);return LEGACY_READ(phase,context);
}
