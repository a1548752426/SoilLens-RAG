import Head from "next/head";

export default function Home() {
  return (
    <>
      <Head>
        <title>SoilLens · 土壤环境智能问答</title>
        <meta
          name="description"
          content="基于原创演示文档和合成样点的土壤重金属智能问答与污染评价。"
        />
      </Head>
      <iframe
        className="demo-frame"
        src="/demo.html"
        title="SoilLens 公开合成演示"
      />
      <style jsx global>{`
        html,
        body,
        #__next {
          width: 100%;
          height: 100%;
          margin: 0;
          overflow: hidden;
          background: #f5f3ea;
        }
        .demo-frame {
          width: 100%;
          height: 100%;
          border: 0;
          display: block;
        }
      `}</style>
    </>
  );
}
