import * as cdk from 'aws-cdk-lib';
import {Stack, Tags} from 'aws-cdk-lib';
import {Construct} from 'constructs';

export class CodeMappingStack extends Stack {
    constructor(scope: Construct, id: string, props?: cdk.StackProps) {
        super(scope, id, props);
        Tags.of(this).add('Project', 'code-field-mapping');
        Tags.of(this).add('ManagedBy', 'cdk');
        
        const bucketName = 'code-mapping-vector-bucket';
        
        const vectorBucket = new cdk.CfnResource(this, 'VectorBucket', {
            type: 'AWS::S3Vectors::VectorBucket',
            properties: {
                VectorBucketName: bucketName,
            },
        });

        const vectorIndex = new cdk.CfnResource(this, 'VectorIndex', {
            type: 'AWS::S3Vectors::Index',
            properties: {
                VectorBucketName: bucketName,
                IndexName: 'code-mapping-vector-index',
                DataType: 'float32',
                Dimension: 1024,
                DistanceMetric: 'cosine',
            },
        });
        vectorIndex.addDependency(vectorBucket);


        new cdk.CfnOutput(this, 'VectorBucketName', {
            value: bucketName,
            description: 'S3 Vectors bucket name',
            exportName: 'CodeMappingVectorBucketName',
        });

        new cdk.CfnOutput(this, 'VectorIndexArn', {
            value: vectorIndex.getAtt('IndexArn').toString(),
            description: 'S3 Vectors index ARN',
            exportName: 'CodeMappingVectorIndexArn',
        });
    }
}
