import * as cdk from 'aws-cdk-lib';
import {Stack, Tags} from 'aws-cdk-lib';
import {Construct} from 'constructs';
import * as s3Vectors from 'cdk-s3-vectors';

export class CodeMappingStack extends Stack {
    constructor(scope: Construct, id: string, props?: cdk.StackProps) {
        super(scope, id, props);
        Tags.of(this).add('Project', 'code-field-mapping');
        Tags.of(this).add('ManagedBy', 'cdk');
        
        // Create a vector bucket
        const vectorBucket = new s3Vectors.Bucket(this, 'VectorBucket', {
            vectorBucketName: 'code-mapping-vector-bucket',
        });

        // Create vector index
        const vectorIndex = new s3Vectors.Index(this, 'VectorIndex', {
            vectorBucketName: vectorBucket.vectorBucketName,
            indexName: 'code-mapping-vector-index',
            dataType: 'float32',
            dimension: 1024,
            distanceMetric: 'cosine',
        });
        vectorIndex.node.addDependency(vectorBucket);

        // Outputs
        new cdk.CfnOutput(this, 'VectorBucketName', {
            value: vectorBucket.vectorBucketName,
            description: 'S3 Vectors bucket name',
            exportName: 'CodeMappingVectorBucketName',
        });

        new cdk.CfnOutput(this, 'VectorIndexName', {
            value: vectorIndex.indexName,
            description: 'S3 Vectors index name',
            exportName: 'CodeMappingVectorIndexName',
        });
    }
}
